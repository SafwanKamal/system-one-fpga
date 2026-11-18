"""Exact C-vs-image head verification plus bounded bridge tests, no board access."""
from pathlib import Path
import hashlib
import json
import subprocess
import struct
import sys
import argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.ddr_image import ImageMachine

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed-intent-host-v1');args=ap.parse_args()
    out=ROOT/'build/v2'/args.name
    out.mkdir(exist_ok=False)
    profile=ROOT/'firmware/typed_intent/generated'
    seal=json.loads((profile/'manifest.json').read_text())
    for p,h in seal['files'].items(): assert sha(profile/p)==h
    image=ROOT/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img'
    assert sha(image)==seal['image_sha256']
    machine=ImageMachine(image.read_bytes());rng=np.random.default_rng(184603)
    cases=[]
    for count in range(1,129):
        rows=np.arange(count,dtype=np.uint16)
        for val in (-128,127,0): cases.append((128,rows,np.full((128,384),val,dtype=np.int8),True))
        cases.append((128,rows,rng.integers(-128,128,(128,384),dtype=np.int8),True))
        # Non-contiguous selected segment rows, including last token.
        rows=np.sort(rng.choice(128,count,replace=False)).astype(np.uint16)
        cases.append((128,rows,rng.integers(-128,128,(128,384),dtype=np.int8),True))
    for tokens,rows in [(0,[0]),(129,[0]),(1,[]),(1,[1]),(2,[1,1]),(2,[1,0]),(1,[0,0])]:
        cases.append((tokens,np.array(rows,dtype=np.uint16),np.zeros((128,384),dtype=np.int8),False))
    expected=[]
    with (out/'inputs.bin').open('wb') as f:
        f.write(struct.pack('<I',len(cases)))
        for tokens,rows,x,valid in cases:
            padded=np.zeros(128,dtype='<u2');padded[:len(rows)]=rows
            f.write(struct.pack('<HH',tokens,len(rows))+padded.tobytes()+x.tobytes())
            if valid:
                logits,scales=machine.head_logits(x,'intent.atis',rows)
                expected.append((1,int(np.argmax(logits*scales)),logits.astype(np.int64)))
            else:expected.append((0,0,np.zeros(18,dtype=np.int64)))
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    rel=out.relative_to(ROOT).as_posix()
    commands=[['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
               '-fno-fast-math','-ffp-contract=off','-fsanitize=address,undefined',
               '-fno-sanitize-recover=all','firmware/typed_intent/typed_intent.c',
               'firmware/typed_intent/typed_mailbox.c',
               'firmware/typed_intent/test_runner.c','-lm','-o',rel+'/head-test'],
              [rel+'/head-test',rel+'/inputs.bin',rel+'/outputs.bin']]
    for i,cmd in enumerate(commands):
        result=subprocess.run(['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--',*cmd],
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/f'command-{i}.log').write_bytes(result.stdout)
        if result.returncode:raise RuntimeError(f'Command {i} failed; preserve log')
    raw=(out/'outputs.bin').read_bytes();assert len(raw)==len(cases)*80
    for i,(ok,label,logits) in enumerate(expected):
        actual=struct.unpack_from('<II18i',raw,80*i)
        assert actual[:2]==(ok,label),(i,actual[:2],ok,label)
        assert np.array_equal(actual[2:],logits),(i,actual[2:],logits)
    files=[p for p in (ROOT/'firmware/typed_intent').rglob('*') if p.is_file()]
    files += [Path(__file__),ROOT/'scripts/v2/freeze_typed_intent.py']
    receipt={'passed':True,'cases':len(cases),'valid_cases':640,'invalid_cases':7,
        'integer_logits_compared':640*18,'all_pool_counts':list(range(1,129)),
        'exact_label_match':True,'bridge_directed_assertions_passed':True,
        'mailbox_word_layout_assertions_passed':True,
        'host_sanitizers':['address','undefined'],'seed':184603,
        'contract_sha256':json.loads((profile/'contract.json').read_text())['contract_sha256'],
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in files},
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'limits':['No target execution or WCET proof','Host tests are not semantic accuracy measurement',
                  'Model-image head reference, not full encoder regression']}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS {len(cases)} cases; {640*18} exact logits and 640 exact labels; bridge assertions')
if __name__=='__main__':main()
