import copy,json
from pathlib import Path
from sysone.v2.retention_comparison_v13 import prepare,HISTORY_SYSTEM,CONTEXT,OUTPUT
ROOT=Path(__file__).resolve().parents[1]
def spec():return json.loads((ROOT/'build/v2/v8-json-retention-v12/bundle/manifest.json').read_text())
def jobs():return prepare(spec(),lambda t:list(t.encode()))
def test_workload_identity_and_independent_reducer():
 s=spec();rs=jobs();assert len(rs)==448
 for c in s['cases']:
  state=copy.deepcopy(c['initial'])
  for i,step in enumerate(c['steps'],1):
   o=step['observation']
   if o:
    if o['status']=='ok':state[o['entity']][0]=o['count']
    state[o['entity']][1]=o['status']
   pair=[j for j in rs if j['case_id']==c['id'] and j['step']==i]
   assert {j['arm'] for j in pair}=={'json','history'}
   assert all(j['state']==state and j['expected']==[state[step['entity']][1],step['entity'],state[step['entity']][0]] for j in pair)
def test_full_history_preserves_all_turns_and_never_current_answer():
 for j in jobs():
  if j['arm']!='history':continue
  p=j['prompt'];assert p.count('<|im_start|>user\n')==j['step']
  assert p.count('<|im_start|>assistant\n')==j['step']
  assert p.count('Tool observation ')==j['step']
  assert p.endswith('<think>\n\n</think>\n\n')
  current=p.rsplit('<|im_start|>user\n',1)[1]
  assert 'State.' not in current and '"status":' not in current.split('\nReport')[1]
  assert current.startswith('Tool observation '+json.dumps(j['observation'],separators=(',',':')))
def test_initial_counts_not_latest_snapshot_in_history_system():
 for c in spec()['cases']:
  r=next(j for j in jobs() if j['case_id']==c['id'] and j['step']==len(c['steps']) and j['arm']=='history')
  sys=r['prompt'].split('<|im_end|>',1)[0]
  assert all('"count":'+str(v[0]) in sys for v in c['initial'].values())
def test_capacity_does_not_truncate_or_mutate_input():
 for j in jobs():
  assert j['input_tokens']==len(j['prompt_ids'])
  assert j['capacity_ok']==(j['input_tokens']+OUTPUT<=CONTEXT)
  if not j['capacity_ok']:assert len(j['prompt_ids'])>CONTEXT-OUTPUT
