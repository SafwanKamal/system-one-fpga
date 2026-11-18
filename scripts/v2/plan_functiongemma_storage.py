"""Checkpoint-derived storage ledger and candidate packed-code qualification.

No hardware ABI, image, quantization-quality or board qualification claim.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from safetensors import safe_open

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.functiongemma_packed_weights import PackedWeights


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--qualification',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    q=json.loads(args.qualification.read_text(encoding='utf-8'))
    assert q['stage']=='complete'
    if digest(args.model/'model.safetensors')!=q['model_sha256']:
        raise ValueError('weight parent differs')
    shapes=q['shape_manifest'];cfg=json.loads((args.model/'config.json').read_text(encoding='utf-8'))
    tokenizer=json.loads((args.model/'tokenizer.json').read_text(encoding='utf-8'))
    vocab=tokenizer['model']['vocab']
    entries=dict(vocab)
    # Added-token decoder text can differ from the BPE model's placeholder.
    by_id={int(i):piece for piece,i in entries.items()}
    if set(by_id)!=set(range(cfg['vocab_size'])):raise ValueError('base vocabulary ID extent differs')
    unsupported_added=[]
    for item in tokenizer.get('added_tokens',[]):
        if 0<=item['id']<cfg['vocab_size']:by_id[item['id']]=item['content']
        else:unsupported_added.append(dict(id=item['id'],content=item['content']))
    pieces=sum(len(by_id[i].encode('utf-8')) for i in range(cfg['vocab_size']))
    decoder_bytes=pieces+(cfg['vocab_size']+1)*4
    base=q['parameter_storage'];embedding=base['embedding_elements']
    norm_elements=sum(int(np.prod(shape)) for name,shape in shapes.items() if 'norm' in name)
    linear_rows=sum(shape[0] for name,shape in shapes.items() if name.endswith('_proj.weight'))
    # One row scale/multiplier record for each shared embedding/projection row.
    scale_rows=linear_rows+cfg['vocab_size']
    options=[]
    for bits in [8,7,6]:
        costs=dict(weight_codes=base['unique_elements']-embedding+embedding*bits//8,
            norm_upgrade_int8_to_int32=norm_elements*3,
            requant_records_8_bytes_each=scale_rows*8,
            int8_kv_2048=base['int8_kv_2048_context_bytes'],
            rotary_tables_int16_two_frequencies=2*2048*(cfg['head_dim']//2)*2*2,
            decoder_piece_pool_plus_uint32_offsets=decoder_bytes,
            activation_scratch_assumption=4*1024*1024,
            firmware_mailbox_assumption=512*1024,
            headers_alignment_assumption=128*1024)
        total=sum(costs.values());margin=256*1024*1024-total
        options.append(dict(embedding_bits=bits,other_matrix_bits=8,costs=costs,
            total_bytes=total,margin_bytes=margin,fits_declared_estimate=margin>=0))
    tests=[]
    with safe_open(args.model/'model.safetensors',framework='numpy') as store:
        # NumPy backend cannot directly decode BF16; use only header here.
        assert store.get_slice('model.embed_tokens.weight').get_shape()==[cfg['vocab_size'],cfg['hidden_size']]
    with safe_open(args.model/'model.safetensors',framework='pt',device='cpu') as store:
        selection=store.get_slice('model.embed_tokens.weight')
        for start in [0,32,cfg['vocab_size']-32]:
            weights=selection[start:start+32,:].float().numpy()
            rng=np.random.default_rng(2026101804+start)
            inputs=rng.integers(-128,128,size=(2,cfg['hidden_size']),dtype=np.int8)
            for bits in [6,7,8]:
                peak=np.max(np.abs(weights),axis=1,keepdims=True)
                scale=np.maximum(peak/((1<<(bits-1))-1),np.finfo(np.float32).tiny)
                codes=np.clip(np.rint(weights/scale),-((1<<(bits-1))-1),(1<<(bits-1))-1).astype(np.int8)
                packed=PackedWeights.from_codes(codes,bits)
                for row in range(32):np.testing.assert_array_equal(packed.gather(row),codes[row])
                np.testing.assert_array_equal(packed.matmul(inputs),inputs.astype(np.int64)@codes.astype(np.int64).T)
                tests.append(dict(first_token_id=start,rows=32,bits=bits,packed_bytes=len(packed.data),
                    exact_code_gather=True,exact_integer_projection=True,
                    diagnostic_weight_rms_error=float(np.sqrt(np.mean((codes*scale-weights)**2)))))
    result=dict(scope='offline candidate storage estimate and lossless integer-code codec; not hardware or task-quality qualification',
        model_sha256=q['model_sha256'],model_config_sha256=q['config_sha256'],
        tokenizer_sha256=digest(args.model/'tokenizer.json'),supported_model_ids_require_bits=18,proposed_token_storage_bits=32,
        unsupported_added_tokens=unsupported_added,input_gate_must_reject_ids_at_or_above=cfg['vocab_size'],
        existing_uint16_token_abi_compatible=False,unique_parameter_elements=base['unique_elements'],
        tied_embedding_projection_required=True,decoder_table_bytes=decoder_bytes,
        decoder_implementation_complete=False,decoder_spec=tokenizer['decoder'],
        options=options,packing_fixtures=tests,hardware_loaded=False,board_contacted=False,
        unsupported=['RTL unpacker and packed layout ABI','full integer decoder and calibration',
            'R5 tokenizer-piece decoder and typed parser integration','compiler/buffer allocation and module ABI',
            'whole-model quantization quality','DDR throughput and terminal-by-D contract qualification'],
        caveat='Fits means the listed estimate fits; no executable image or complete storage allocation exists.',
        source_sha256={str(p):digest(p) for p in [Path(__file__),ROOT/'src/sysone/v2/functiongemma_packed_weights.py']})
    (args.out/'storage-plan.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(options=[dict(bits=x['embedding_bits'],bytes=x['total_bytes'],margin=x['margin_bytes']) for x in options],fixtures=len(tests),decoder_table_bytes=decoder_bytes)))


if __name__=='__main__':main()
