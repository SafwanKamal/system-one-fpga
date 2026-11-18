"""Admit the parameterized grouped cuts; preserve earlier candidates."""
import hashlib,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 return re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)',p.read_text())
def main():
 tested=ROOT/'build/v2/rtl-pipeline-cuts-check'
 assert json.loads((tested/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
 prior=ROOT/'build/v2/rtl-probability-drain-check'
 assert json.loads((prior/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
 base=json.loads((ROOT/'build/v2/kr260-opt-capture-flags-large/regression.json').read_text())
 directories={'wide':'build/v2/rtl-wide-check/vectors','l12':'simulation/v2/vectors/kr260','one-word':'build/v2/rtl-batch3-check/one-word-vectors','boundary':'build/v2/rtl-batch-check/boundary-vectors','h1024':'build/v2/kr260-dot7-h1024-eight-vectors'}
 checks={}
 for name,want in base['checks'].items():
  path=tested/f'{name}.log';actual=rows(path);prototype=rows(prior/f'{name}.log')
  assert len(actual)==len(want['tokens']) and [int(r[1]) for r in actual]==want['tokens']
  assert all(r[2]=='0' and r[4]=='0' for r in actual)
  assert actual==prototype, f'Parameterized numerical/cycle profile changed: {name}'
  assert 'FEATURES 535907ff' in path.read_text()
  for filename,digest in want['vectors_sha256'].items():assert sha(ROOT/directories[name]/filename)==digest,f'Golden vector changed: {name}/{filename}'
  checks[name]={'log_sha256':sha(path),'tokens':want['tokens'],'encoder_clocks':[int(r[5]) for r in actual],'request_clocks':[int(r[6]) for r in actual],'prototype_cycles_identical':True,'vectors_sha256':want['vectors_sha256']}
 legacy=tested/'nexys-default.log';original=ROOT/'build/v2/rtl-capture-flags-check/nexys-default.log'
 pattern=r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
 actual_default=re.findall(pattern,legacy.read_text());original_default=re.findall(pattern,original.read_text())
 assert len(actual_default)==2 and actual_default==original_default
 assert 'PASS: encoder layer bit-exact, 2 cases, 39216 words compared' in legacy.read_text()
 for name in ['attention-probability-ooc','linear-drain-ooc']:
  assert json.loads((ROOT/f'build/v2/{name}/summary.json').read_text())['complete' if name=='linear-drain-ooc' else 'completed']
 assert json.loads((ROOT/'build/v2/drain-partial-check/summary.json').read_text())['passed']
 assert json.loads((ROOT/'build/v2/rtl-probability-check/review.json').read_text())['numerical_cases']==32
 digests={name:digest for digest,name in (line.split(maxsplit=1) for line in (tested/'source-sha256.txt').read_text().splitlines())}
 sources=list(base['rtl_sha256'])+['rtl/v2/common/attention_probability.sv','rtl/v2/common/linear_drain_select.sv']
 for n in sources:assert sha(ROOT/n)==digests[n],f'Edit under numerical test: {n}'
 output=ROOT/'build/v2/kr260-opt-pipeline-cuts-large'
 if output.exists():raise ValueError('Preserve existing pipeline candidate')
 for n in sources:
  target=output/'rtl-snapshot'/n.removeprefix('rtl/v2/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,target)
 profile={**base['profile'],'probability_pipeline':1,'pipelined_drain_select':1}
 evidence={'candidate':'pipeline-cuts-large','target_mhz':200,'read_latency':5,'profile':profile,'capability_word':'0x535907ff','numerical_cases':32,'checks':checks,'nexys_default_cycles_unchanged':True,'rtl_sha256':{n:digests[n] for n in sources},'routed':False,'hardware_qualified':False}
 (output/'regression.json').write_text(json.dumps(evidence,indent=2)+'\n')
 (output/'completion-status.json').write_text(json.dumps({'state':'numerical_ready','updated_utc':datetime.now(timezone.utc).isoformat()},indent=2)+'\n')
 print('PASS: 32 cases equal prototype, Nexys default outputs/cycles preserved,21 sources frozen')
if __name__=='__main__':main()
