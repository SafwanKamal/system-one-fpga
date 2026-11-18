"""Fresh matched CPU/FPGA retention chains with measured input-token parity."""
import copy
import random
from .v8_json_retention_v9 import manifest as original_manifest,prepare as original_prepare,execute,summarize as original_summarize
from .v8_json_retention_v10 import prompt

VERSION='v8-json-retention-v12'


def manifest():
    spec=copy.deepcopy(original_manifest())
    spec.update(version=VERSION,phase='paired-evaluation',evaluation_seed_base=202610211300,
        prompt_policy='frozen v10-r3 status-copy instruction, logical prefix unchanged',
        cpu_framing='v11-r2 binary file framing; every actual CLI prompt ID verified',
        board_access=True,closed_loop_included=False,full_sweep_started=False,
        scope='six fixed fresh sequences, paired on both backends; not the full system sweep')
    for index,case in enumerate(spec['cases']):
        seed=202610211300+index;rng=random.Random(seed);swap=bool(rng.getrandbits(1))
        case.update(id='paired-'+case['id'],split='fresh-paired-evaluation',seed=seed,swap_entities=swap)
        case['initial']={'A':[rng.randrange(301,650),'ok'],'B':[rng.randrange(651,950),'ok']}
        for step in case['steps']:
            if step['observation'] and step['observation']['status']=='ok':step['observation']['count']=rng.randrange(301,950)
        if case['family']=='long-gap' and len(case['steps'])==32:case['steps'][0]['observation']['status']='error'
        if swap:
            other=lambda e:'B' if e=='A' else 'A'
            case['initial']={other(e):value for e,value in case['initial'].items()}
            for step in case['steps']:
                step['entity']=other(step['entity'])
                if step['observation']:step['observation']['entity']=other(step['observation']['entity'])
    return spec


def prepare(encode):
    spec=manifest();jobs=original_prepare(spec,encode)
    for job in jobs:
        job['policy']='status-copy';job['prompt']=prompt(job['state'],job['entity'],'status-copy')
        job['prompt_ids']=encode(job['prompt']);job['input_tokens']=len(job['prompt_ids'])
        if job['input_tokens']+job['output_tokens']>spec['context_limit']:raise ValueError('Frozen context budget exceeded')
    return spec,jobs


def summarize(rows):
    result=original_summarize(rows);result['version']=VERSION
    result['comparison']='Fresh paired CPU/FPGA evaluation with actual input IDs verified; not paired with older versions.'
    return result
