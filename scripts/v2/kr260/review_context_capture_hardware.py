"""Review actual frozen-suite and board receipts; never infer hardware success from routing."""
from pathlib import Path
import hashlib,json,re,struct,statistics
from datetime import datetime,timezone
from validate_h1024 import load_vectors
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 b=ROOT/'build/v2/kr260-opt-attention-context-capture-large';v=ROOT/'build/v2/context-capture-board-validation'
 assert (v/'validation-status.txt').read_text().strip()=='passed'
 receipt=json.loads((v/'receipt.json').read_text());assert receipt['exit_code']==0
 state=json.loads((v/'final-state.json').read_text())
 assert state['id']=='0x53595332' and state['build']=='0x20804004' and state['features']=='0x5377ffff'
 assert state['clock_hz']==199999998 and state['clock1_hz']==199999998
 assert state['reserved_base']==0x60000000 and state['reserved_bytes']==268435456
 assert state['recovery_125_files_verified'] and state['candidate_files_verified']
 assert state['firmware']=='sysone-v2-attention-context-capture.bit.bin'
 assert '33,916,928 bytes' in (v/'final-model-restore.log').read_text() and 'identical after read-back' in (v/'final-model-restore.log').read_text()
 app=json.loads((v/'app.json').read_text());assert app['capability_word']=='0x5377ffff' and app['fabric_context_capture']==1
 assert app==json.loads((b/'sysone-v2-attention-context-capture/build.json').read_text())
 lengths={}
 for name,directory,count in [('h1024','h1024-vectors',8),('query-group','query-group-vectors',4)]:
  report=json.loads((v/f'{name}.json').read_text());manifest,_,cases=load_vectors(b/directory)
  assert report['clock_hz']==199999998 and report['image_sha256']==manifest['sha256']
  assert len(report['cases'])==count
  for actual,expected in zip(report['cases'],cases,strict=True):
   digest=hashlib.sha256(expected[-1]).hexdigest()
   assert actual['bit_exact'] and actual['tokens']==expected[0] and actual['hidden']==1024
   assert actual['hardware_sha256']==actual['expected_sha256']==digest
  lengths[name]=[c['tokens'] for c in report['cases']]
 check=(v/'check.log').read_text();smoke=re.findall(r'(\d+) tokens: X bit-exact; board: encoder ([\d,]+) clocks',check)
 assert [int(n) for n,_ in smoke]==[1,2,3,4,5,12,64,128] and 'values differ' not in check
 suite=json.loads((ROOT/'build/v2/eval/minilm-l12-v1-matched.json').read_text())
 report=json.loads((v/'eval.json').read_text());assert report['complete'] and report['backend']=='kr260' and report['clock_hz']==199999998
 assert report['verification']=={'exact':350,'total':350} and len(report['cases'])==350
 assert report['suite_sha256']==suite['suite_sha256'] and report['image_sha256'] in suite['image_sha256'].values()
 frozen={c['id']:c for c in suite['cases']};assert len(frozen)==350
 for actual in report['cases']:
  expected=frozen.pop(actual['id']);ids=expected['ids']
  assert actual['bit_exact'] is True and actual['hidden_sha256']==expected['hidden_sha256']
  assert actual['ids_sha256']==hashlib.sha256(struct.pack('<'+'H'*len(ids),*ids)).hexdigest()
 assert not frozen
 regression=json.loads((b/'regression.json').read_text());assert len(regression['rtl_sha256'])==23
 for n,h in regression['rtl_sha256'].items():assert sha(ROOT/n)==h,n
 archive=ROOT/'build/v2/kr260-app-attention-context-capture-large.tar.gz'
 assert sha(archive)==receipt['archive_sha256']=='ecd320163baa3c289c64e069186497974d4703039df4a455bc8620d357d7ec99'
 receipt['hardware_qualified']=True
 receipt['reviewed_utc']=datetime.now(timezone.utc).isoformat()
 (v/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 names=['receipt.json','final-state.json','final-model-restore.log','app.json','h1024.json','query-group.json','check.log','eval.json','validation-status.txt','recovery-app.txt']
 result={'candidate':'attention-context-capture-large','hardware_qualified':True,'reviewed_utc':datetime.now(timezone.utc).isoformat(),'clock_hz':199999998,'capability_word':'0x5377ffff','routed_setup_slack_ns':.101,'routed_hold_slack_ns':.010,'h1024_cases':8,'query_group_cases':4,'l12_smoke_cases':8,'frozen_l12_cases':350,'all_outputs_bit_exact':True,'archive_sha256':sha(archive),'recovery_125_preserved':True,'boot_reservation_unchanged':True,'l12_model_restored_readback_exact':True,'fixture_lengths':lengths,'report_sha256':{n:sha(v/n) for n in names},'stage':'Hardware-qualified 200 MHz package; no 300 MHz or quality improvement claim'}
 (b/'hardware-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
