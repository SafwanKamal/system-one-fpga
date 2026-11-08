"""Pinned Qwen tokenizer: native normalization/splitting, compiled ranked BPE.

Only trusted build artifacts are unpickled. No model tensors or NN backend.
"""
import hashlib
import json
import pickle
import re
import sys


class Vocabulary:
    def __init__(self, package):
        sys.path.insert(0, str(package/'tokenizer-runtime'))
        from tokenizers import Regex, normalizers, pre_tokenizers
        raw=(package/'tokenizer-bpe.pkl').read_bytes()
        expected=json.loads((package/'tokenizer-bpe-source.json').read_text())
        if hashlib.sha256(raw).hexdigest()!=expected['compiled_sha256']:
            raise RuntimeError('Compiled tokenizer differs from its pinned build')
        data=pickle.loads(raw)
        self.ranks=data['ranks'];self.pieces=data['pieces'];self.characters=data['characters']
        self.added=data['added'];self.special=data['special']
        self.pattern=re.compile('('+'|'.join(re.escape(x) for x in sorted(self.added,key=len,reverse=True))+')')
        self.normalizer=normalizers.NFC()
        self.split=pre_tokenizers.Sequence([
            pre_tokenizers.Split(Regex(data['pattern']),behavior='isolated'),
            pre_tokenizers.ByteLevel(add_prefix_space=False,trim_offsets=False,use_regex=False)])

    def encode_text(self,text):
        ids=[]
        for fragment in self.pattern.split(text):
            if fragment in self.added:
                ids.append(self.added[fragment]);continue
            for word,_ in self.split.pre_tokenize_str(self.normalizer.normalize_str(fragment)):
                tokens=[self.characters[c] for c in word]
                while len(tokens)>1:
                    best=None
                    for i in range(len(tokens)-1):
                        pair=(tokens[i]<<32)|tokens[i+1];value=self.ranks.get(pair)
                        if value is not None and (best is None or value[0]<best[0]):best=(value[0],pair,value[1])
                    if best is None:break
                    merged=[];i=0
                    while i<len(tokens):
                        if i+1<len(tokens) and ((tokens[i]<<32)|tokens[i+1])==best[1]:
                            merged.append(best[2]);i+=2
                        else:merged.append(tokens[i]);i+=1
                    tokens=merged
                ids.extend(tokens)
        return ids

    def encode(self,path):return self.encode_text(path.read_text(encoding='utf-8'))
    def piece(self,token):
        if token in self.special:return b''
        if not 0<=token<len(self.pieces) or self.pieces[token] is None:raise ValueError('Token outside pinned vocabulary')
        return self.pieces[token]
    def close(self):pass
