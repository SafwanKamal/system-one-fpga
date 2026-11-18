"""Freeze context capture only after fresh full-profile proof and isolated mapping review."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re,shutil,sys
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)',p.read_text())
def main():
 tested=ROOT/'build/v2/rtl-context-capture-parameter-check'
 proto=ROOT/'build/v2/rtl-attention-context-capture-check'
 previous=ROOT/'build/v2/kr260-opt-request-window-embed-large'
 base=json.loads((previous/'regression.json').read_text())
 assert json.loads((tested/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
 assert json.loads((proto/'review.json').read_text())['exact_outputs_encoder_request_cycles']
 ooc=ROOT/'build/v2/attention-context-capture-ooc/review.json'
 review=json.loads(ooc.read_text());assert review['accepted_for_parameterized_integration']
 for n,h in review['source_sha256'].items():assert sha(ROOT/n)==h,n
 checks={k:dict(v) for k,v in base['checks'].items()}
 for n,c in {'wide':8,'l12':8,'one-word':5,'boundary':3,'h1024':8,'head32':4,'partial':6}.items():
  actual=rows(tested/f'{n}.log');assert len(actual)==c and actual==rows(proto/f'{n}.log'),n
  assert all(x[2]=='0' and x[4]=='0' for x in actual)
  assert 'FEATURES 5377ffff ' in (tested/f'{n}.log').read_text(),n
  if n in checks:checks[n].update(log_sha256=sha(tested/f'{n}.log'),prototype_cycles_identical=True,encoder_clocks=[int(x[5]) for x in actual],request_clocks=[int(x[6]) for x in actual])
 pat=r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
 default=re.findall(pat,(tested/'nexys-default.log').read_text());assert len(default)==2 and default==re.findall(pat,(proto/'nexys-default.log').read_text())
 for group,directory in {'wide':'build/v2/rtl-wide-check/vectors','l12':'simulation/v2/vectors/kr260','one-word':'build/v2/rtl-batch3-check/one-word-vectors','boundary':'build/v2/rtl-batch-check/boundary-vectors','h1024':'build/v2/kr260-dot7-h1024-eight-vectors'}.items():
  for n,h in base['checks'][group]['vectors_sha256'].items():assert sha(ROOT/directory/n)==h,n
 for n,h in base['query_group_vectors_sha256'].items():assert sha(ROOT/'build/v2/attention16-head32-vectors'/n)==h,n
 for n,h in base['component_proofs_sha256'].items():assert sha(ROOT/n)==h,n
 digests={n:h for h,n in (line.split(maxsplit=1) for line in (tested/'source-sha256.txt').read_text().splitlines())}
 sources=list(base['rtl_sha256']);assert len(set(sources))==23
 for n in sources:assert sha(ROOT/n)==digests[n],n
 out=ROOT/'build/v2/kr260-opt-attention-context-capture-large';assert not out.exists()
 if sys.argv[1:]==['--validate-only']:
  print('PASS36KR+6partial+2Nexys,23sources,features,prototype/defaultcycles,fixtures,component proofs');return
 assert not sys.argv[1:]
 for n in sources:
  target=out/'rtl-snapshot'/n.removeprefix('rtl/v2/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,target)
 result={**base,'candidate':'attention-context-capture-large','capability_word':'0x5377ffff','checks':checks,'profile':{**base['profile'],'fabric_context_capture':1},'rtl_sha256':{n:digests[n] for n in sources},'component_proofs_sha256':{**base['component_proofs_sha256'],'build/v2/attention-context-capture-ooc/review.json':sha(ooc),'build/v2/rtl-attention-context-capture-check/review.json':sha(proto/'review.json')},'routed':False,'hardware_qualified':False}
 (out/'regression.json').write_text(json.dumps(result,indent=2)+'\n')
 (out/'completion-status.json').write_text(json.dumps({'state':'numerical_ready','updated_utc':datetime.now(timezone.utc).isoformat()})+'\n')
 print('PASS23sources frozen for context-capture200MHz synthesis; no routing')
if __name__=='__main__':main()
