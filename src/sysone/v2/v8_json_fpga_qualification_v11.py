"""Small frozen CPU/FPGA qualification of the v10-r3 retention prompt."""
import copy
import random
from .v8_json_retention_v9 import prepare as prepare_v9,execute
from .v8_json_retention_v10 import prompt

VERSION='v8-json-retention-v11-r2'


def cpu_prompt_file_bytes(text):
    # llama-completion removes one final LF from file input. Compensate at the
    # transport boundary; verbose token IDs must still match the frozen prompt.
    return (text+'\n').encode('utf-8')


def prepare(encode):
    cases=[]
    for index,(e,other) in enumerate((('A','B'),('B','A'))):
        rng=random.Random(202610211201+index)
        def event(entity,status):
            return dict(entity=entity,status=status,**({'count':rng.randrange(301,950)} if status=='ok' else {}))
        sequence=[(e,'ok',e),(other,'ok',e),(e,'missing',e),(other,'error',e),
                  (None,None,other),(e,'error',e),(other,'missing',e),(e,'ok',e)]
        cases.append(dict(id=f'qual-{index+1}',mode='retention',family='qualification',split='qualification',
            seed=202610211201+index,initial={'A':[rng.randrange(301,650),'ok'],'B':[rng.randrange(651,950),'ok']},
            steps=[dict(entity=q,observation=event(entity,status) if entity else None) for entity,status,q in sequence]))
    spec=dict(version=VERSION,cases=cases,context_limit=256,output_budget=48,maximum_inferences=20,
              prompt_policy='exact v10-r3 frozen status-copy prompt; no tuning',
              board_access=True,closed_loop_included=False,full_sweep_started=False,
              repeats='steps4 and6 from each chain; compare exact FPGA token IDs',
              gates='all20 records parsed/correct per backend, all inputs aligned, semantic agreement, exact FPGA repeats, before/after causal fixtures and deployment identity')
    # Reuse trusted-observation reducer and metadata, replacing only repeat selection.
    base=prepare_v9(spec,encode);jobs=[]
    for c in cases:
        chain=[copy.deepcopy(j) for j in base if j['case_id']==c['id'] and j['suite']=='primary']
        for row in chain:
            row['policy']='status-copy';row['prompt']=prompt(row['state'],row['entity'],'status-copy')
            row['prompt_ids']=encode(row['prompt']);row['input_tokens']=len(row['prompt_ids'])
            if row['input_tokens']+48>256:raise ValueError('Qualification input capacity')
        jobs.extend(chain)
        for i in (3,5):
            r=copy.deepcopy(chain[i]);r.update(id='repeat-'+r['id'],suite='repeat',repeat_of=r['id']);jobs.append(r)
    return spec,jobs
