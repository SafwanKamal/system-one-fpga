"""Compile pinned HF BPE tables; check exact IDs against the official tokenizer."""
import ast,hashlib,json,pickle,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v8'
sys.path.insert(0,str(ROOT/'src'))
from tokenizers import Tokenizer
from sysone.v2.qwen_tokenizer_v1 import Vocabulary

def main():
    raw=(BUILD/'tokenizer.json').read_bytes();d=json.loads(raw);m=d['model']
    assert hashlib.sha256(raw).hexdigest()==json.loads((BUILD/'tokenizer-correctness.json').read_text())['sha256']
    assert m['type']=='BPE' and not any(m[k] for k in ['dropout','unk_token','continuing_subword_prefix','end_of_word_suffix','fuse_unk','byte_fallback','ignore_merges'])
    assert d['normalizer']=={'type':'NFC'}
    for added in d['added_tokens']:
        assert not any(added[k] for k in ['single_word','lstrip','rstrip','normalized'])
    pt=d['pre_tokenizer']['pretokenizers'];assert d['pre_tokenizer']['type']=='Sequence' and len(pt)==2
    assert pt[0]['type']=='Split' and pt[0]['behavior']=='Isolated' and not pt[0]['invert']
    assert pt[1]==dict(type='ByteLevel',add_prefix_space=False,trim_offsets=False,use_regex=False)
    vocab=m['vocab'];ranks={}
    for rank,(left,right) in enumerate(m['merges']):
        key=(vocab[left]<<32)|vocab[right];assert key not in ranks
        ranks[key]=(rank,vocab[left+right])
    bs=list(range(33,127))+list(range(161,173))+list(range(174,256));cs=bs.copy();n=0
    for b in range(256):
        if b not in bs:bs.append(b);cs.append(256+n);n+=1
    decoder={chr(c):b for b,c in zip(bs,cs)}
    size=max(list(vocab.values())+[x['id'] for x in d['added_tokens']])+1
    pieces=[None]*size
    for word,index in vocab.items():pieces[index]=bytes(decoder[c] for c in word)
    for x in d['added_tokens']:pieces[x['id']]=x['content'].encode()
    data=dict(ranks=ranks,pieces=pieces,characters={c:vocab[c] for c in decoder},added={x['content']:x['id'] for x in d['added_tokens']},special={x['id'] for x in d['added_tokens'] if x['special']},pattern=pt[0]['pattern']['Regex'])
    compiled=pickle.dumps(data,protocol=4);(BUILD/'tokenizer-bpe.pkl').write_bytes(compiled)
    source=dict(source_sha256=hashlib.sha256(raw).hexdigest(),compiled_sha256=hashlib.sha256(compiled).hexdigest(),merges=len(ranks),bytes=len(compiled),normalization='native NFC',pretokenization='native official Split + ByteLevel',BPE='ordered minimum-rank adjacent pairs; no NN')
    (BUILD/'tokenizer-bpe-source.json').write_text(json.dumps(source,indent=2)+'\n')
    fast=Vocabulary(BUILD);reference=Tokenizer.from_file(str(BUILD/'tokenizer.json'))
    result=json.loads((BUILD/'board/results/10-one-cold-real-command/stdout').read_text())
    syntax=ast.parse((ROOT/'scripts/v2/run_qwen_fpga_command_v7.py').read_text())
    nodes=[n for n in syntax.body if (isinstance(n,ast.FunctionDef) and n.name=='prompt_for') or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in n.targets))]
    scope={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'prompt-extract','exec'),scope);prompt_for=scope['prompt_for']
    texts=[prompt_for(result['query']),result['generated_text'],"can't we're 123456\r\n\t tabs  ",'/tmp/caf\u00e9/e\u0301/\u65e5\u672c/\U0001f600.json', '<think>plan</think><tool_call>{}</tool_call>', '  leading\n\ntrailing  ', '<|im_start|>user\n<|im_end|>', 'x'*400]
    for text in texts:assert fast.encode_text(text)==reference.encode(text,add_special_tokens=False).ids,repr(text)
    assert fast.encode_text(texts[0])==result['prompt_ids']
    assert b''.join(fast.piece(i) for i in result['generated_ids'])==result['generated_text'].encode()
    source.update(exact_ID_cases=len(texts),prior_prompt_ids_equal=True,prior_generated_bytes_equal=True)
    (BUILD/'tokenizer-bpe-source.json').write_text(json.dumps(source,indent=2)+'\n')
    print(json.dumps(source))

if __name__=='__main__':main()
