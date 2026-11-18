"""Export training/tuning only; never export audit targets or modify a model."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tokenizers

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from maintenance_revision2 import verify,sha,dump,read_rows,write_rows
from sysone.v2.maintenance.revision2 import prompt,CONTEXT
from sysone.v2.maintenance.schema import encode
from sysone.v2.qwen_tokenizer_v1 import Vocabulary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work',type=Path,default=ROOT/'build/v2/maintenance-pilot-v2-context1024')
    a=ap.parse_args();verify(a.work)
    out=a.work/'sft-export';out.mkdir(exist_ok=False)
    vocab=Vocabulary(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment')
    eos=vocab.encode_text('<|im_end|>')
    if eos!=[151645]:raise RuntimeError('Unexpected response terminator')
    counts={};maxima={}
    try:
        for split in ('train','tuning'):
            records=[]
            for case in read_rows(a.work/(split+'.jsonl')):
                p=prompt(case);completion=encode(case['gold'])
                prefix=vocab.encode_text(p);target=vocab.encode_text(completion)+eos
                if len(prefix)+len(target)>CONTEXT:raise RuntimeError('SFT target exceeds1024')
                records.append(dict(id=case['id'],split=split,prompt=p,completion=completion,
                    input_ids=prefix+target,labels=[-100]*len(prefix)+target,
                    prompt_tokens=len(prefix),completion_tokens=len(target)))
            write_rows(out/(split+'.jsonl'),records)
            counts[split]=len(records);maxima[split]=max(len(r['input_ids']) for r in records)
    finally:vocab.close()
    shutil.copyfile(__file__,out/'export_source.py')
    dump(out/'manifest.json',dict(context=CONTEXT,counts=counts,max_total_tokens=maxima,
        source_sha256={s:sha(a.work/(s+'.jsonl')) for s in ('train','tuning')},
        files_sha256={s:sha(out/(s+'.jsonl')) for s in ('train','tuning')},
        audit_exported=False,model_trained=False,board_access=False,
        prompt_loss_mask=-100,eos_id=151645,system_contract='full schema, no demonstrations',
        data_quality='programmatic development pilot; not human-reviewed industrial data'))
    verify(a.work);print((out/'manifest.json').read_text(),flush=True)


if __name__=='__main__':main()
