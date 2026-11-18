"""Inference adapter for clean-data partial checkpoints; never reads gold calls."""
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from .general_tool_encoder import ToolEncoder, KINDS, scalar_from_span
from .general_training_v2 import encoder_text, source_tokens
from .general_schema_annotations import adapt_tool
from .general_tools import validate_calls, parse_functiongemma


class InferenceFailure(ValueError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


class CleanInference:
    def __init__(self, family, model_path, checkpoint=None, encoder_tokens=256):
        self.encoder = family == 'encoder'
        if family not in ('encoder', 'functiongemma'):
            raise ValueError('unknown family')
        torch.manual_seed(2026101702)
        self.tok = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = (ToolEncoder(model_path, max_calls_per_tool=4) if self.encoder else
                      AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, dtype=torch.float32))
        self.encoder_tokens = encoder_tokens
        if checkpoint is not None:
            saved = torch.load(checkpoint, map_location='cpu', weights_only=False)
            if saved['manifest']['family'] != family:
                raise ValueError('checkpoint family mismatch')
            if saved['manifest']['arguments']['model'] != str(model_path):
                raise ValueError('official parent path differs')
            keys = set(saved['trainable_state'])
            if self.encoder:
                layers = len(self.model.encoder.encoder.layer)
                expected = {n for n,_ in self.model.named_parameters() if
                            n.startswith(('count.', 'kind.', 'span.',
                                          f'encoder.encoder.layer.{layers-2}.',
                                          f'encoder.encoder.layer.{layers-1}.'))}
            else:
                layers = len(self.model.model.layers)
                expected = {n for n,_ in self.model.named_parameters() if
                            n.startswith((f'model.layers.{layers-2}.', f'model.layers.{layers-1}.'))}
            if keys != expected:
                raise ValueError('partial checkpoint key set differs')
            result = self.model.load_state_dict(saved['trainable_state'], strict=False)
            if result.unexpected_keys:
                raise ValueError('unexpected checkpoint keys')
        self.model.requires_grad_(False)
        self.model.eval()
        self.stops = [] if self.encoder else list(dict.fromkeys(
            list(self.model.config.eos_token_id) + [self.tok.convert_tokens_to_ids(t)
            for t in ('<end_of_turn>', '<start_function_response>')]))

    def __call__(self, query, tools):
        tools = [adapt_tool(t) for t in tools]
        if len(tools)>8:
            raise InferenceFailure('tool-count profile')
        return self._encoder(query, tools) if self.encoder else self._generator(query, tools)

    def _generator(self, query, tools):
        messages = [dict(role='developer', content='You are a model that can do function calling with the following functions'),
                    dict(role='user', content=query)]
        text = self.tok.apply_chat_template(messages,
            tools=[dict(type='function', function=t) for t in tools],
            add_generation_prompt=True, tokenize=False)
        ids = self.tok.encode(text, add_special_tokens=False)
        if len(ids)+256>2048:
            raise InferenceFailure('prompt/output context profile', prompt_tokens=len(ids))
        with torch.inference_mode():
            output = self.model.model(input_ids=torch.tensor([ids]), use_cache=True)
            cache = output.past_key_values
            token = int(self.model.lm_head(output.last_hidden_state[:,-1,:]).argmax(-1)[0])
            emitted = [token]
            first = time.perf_counter_ns()
            while token not in self.stops and len(emitted)<256:
                output = self.model.model(input_ids=torch.tensor([[token]]), past_key_values=cache, use_cache=True)
                cache = output.past_key_values
                token = int(self.model.lm_head(output.last_hidden_state[:,-1,:]).argmax(-1)[0])
                emitted.append(token)
        raw = self.tok.decode(emitted, skip_special_tokens=False).strip()
        details = dict(raw_output=raw, prompt_tokens=len(ids), output_tokens=len(emitted), first_token_ns=first)
        try:
            if token not in self.stops:
                raise ValueError('output work cap exhausted')
            return parse_functiongemma(raw, tools), details
        except (ValueError, TypeError, KeyError) as exc:
            raise InferenceFailure(str(exc), **details) from exc

    def _encoder(self, query, tools):
        calls, passes = [], 0
        def predict(tool, key=None, slot=0):
            nonlocal passes
            question, lower = encoder_text(tool, key, slot)
            enc = self.tok(question, query, truncation=False, return_offsets_mapping=True)
            if len(enc['input_ids'])>self.encoder_tokens:
                raise ValueError('encoder input profile')
            with torch.inference_mode():
                outputs = self.model({k:torch.tensor([v]) for k,v in enc.items() if k!='offset_mapping'})
            passes += 1
            return enc, outputs, question, lower
        try:
            for tool in tools:
                _, (counts,_,_), _,_ = predict(tool)
                count = int(counts.argmax(-1)[0])
                if count == 5:
                    raise ValueError('call-count overflow')
                for slot in range(count):
                    if len(calls)>=4:
                        raise ValueError('total-call profile')
                    arguments = {}
                    for key,spec in tool['parameters']['properties'].items():
                        enc,(_,kinds,spans),question,lower = predict(tool,key,slot)
                        kind = KINDS[int(kinds.argmax(-1)[0])]
                        if kind in ('omit','unrepresentable'):
                            if kind=='unrepresentable' or key in tool['parameters'].get('required',[]):
                                raise ValueError('missing or unrepresentable argument')
                            continue
                        if kind == 'span':
                            valid = source_tokens(enc, lower)
                            if not valid:
                                raise ValueError('no eligible value tokens')
                            a = max(valid,key=lambda i:float(spans[0,i,0]))
                            seq = enc.sequence_ids()[a]
                            ends = [i for i in valid if a<=i<a+64 and enc.sequence_ids()[i]==seq]
                            b = max(ends,key=lambda i:float(spans[0,i,1]))
                            text = query if seq==1 else question
                            arguments[key] = scalar_from_span(text[enc['offset_mapping'][a][0]:enc['offset_mapping'][b][1]], spec)
                        else:
                            arguments[key] = {'true':True,'false':False,'null':None,
                                'empty_string':'','empty_array':[],'empty_object':{}}[kind]
                    calls.append(dict(name=tool['name'],arguments=arguments))
            validate_calls(calls, tools)
            return calls, dict(encoder_passes=passes)
        except (ValueError,TypeError,KeyError) as exc:
            raise InferenceFailure(str(exc), encoder_passes=passes) from exc
