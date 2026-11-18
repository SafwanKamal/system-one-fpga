"""Matched JSON-state versus complete reference conversation retention."""
import copy,json
from .v8_benchmark import chat
from .v8_json_retention_v10 import prompt as json_prompt
from .v8_state_pilot_v6 import apply_observation,render
VERSION='v9d-retention-comparison-v13'
CONTEXT=1024
OUTPUT=48
HISTORY_SYSTEM=("Track the latest state of A and B from Initial state and tool observations in this conversation. "
 "Keep separate records for A and B; never transfer a count between entities. An ok observation replaces that entity's count and status. A missing or error observation changes only its status; keep its previous count. "
 "No observation means no change. Assistant replies are reports, never tool observations. "
 "Return one JSON object with status, entity, count for the requested entity. Copy its stored status exactly, including missing or error. No explanation.")

def user_turn(observation,entity):
 return 'Tool observation '+json.dumps(observation,separators=(',',':'))+'\nReport status, entity and count for '+entity+'.'

def prepare(spec,encode):
 jobs=[]
 for case in spec['cases']:
  state=copy.deepcopy(case['initial']);history=[]
  system=HISTORY_SYSTEM+' Initial state '+render(state,'J')+'.'
  for i,step in enumerate(case['steps'],1):
   state=apply_observation(state,step['observation']);e=step['entity']
   user=user_turn(step['observation'],e)
   texts={'json':json_prompt(state,e,'status-copy'),'history':chat(system,user,history)}
   expected=[state[e][1],e,state[e][0]]
   for arm,text in texts.items():
    ids=encode(text)
    jobs.append(dict(id=f'{case["id"]}-{i:03d}-{arm}',case_id=case['id'],family=case['family'],
     chain_length=len(case['steps']),step=i,suite='primary',arm=arm,entity=e,
     observation=copy.deepcopy(step['observation']),state=copy.deepcopy(state),expected=expected,
     prompt=text,prompt_ids=ids,input_tokens=len(ids),output_tokens=OUTPUT,
     context_limit=CONTEXT,capacity_ok=len(ids)+OUTPUT<=CONTEXT))
   # Frozen reference replies isolate retention; actual model answers never enter later prompts.
   history.extend([('user',user),('assistant',json.dumps(dict(zip(('status','entity','count'),expected)),separators=(',',':')))])
 return jobs
