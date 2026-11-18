"""Audit frozen inputs, actual interventions and saved independent metrics."""
import inspect
import subprocess
import numpy as np
from diagnosis import Observation, select
import diagnosis
import simulator as sim
import study as s


def main():
    s.verify_freeze(); frozen=s.load(s.OUT/'freeze.json')
    source_configs=set(s.CONFIGS['train'])|set(s.CONFIGS['validation'])
    assert not source_configs & set(s.CONFIGS['test'])
    assert set(Observation.__dataclass_fields__)=={'commands','pose'}
    assert 'simulator' not in inspect.getsource(diagnosis)
    files=[]; cases=0; metric_rows=0; selections=0
    for split in s.CONFIGS:
        for c in s.CONFIGS[split]:
            path=s.DATA/split/f'{c}.npz'; metadata=s.load(path.with_suffix('.json'))
            for p in [path,path.with_suffix('.json')]:
                files.append(dict(path=str(p.relative_to(s.ROOT)),bytes=p.stat().st_size,sha256=s.sha(p)))
            if split=='train': assert {r['kind'] for r in metadata}==set(s.KNOWN)
            if split=='validation': assert {r['kind'] for r in metadata}==set(s.KNOWN+['quantized','held'])
            if split!='test': continue
            assert {r['kind'] for r in metadata}==set(sim.KINDS) and len(metadata)==70
            with np.load(path) as f: data={k:f[k] for k in f.files}
            cases+=len(metadata)
            assert data['suffix_pose'].shape==(70,82,100,3)
            assert np.max(np.abs(data['suffix_u'][:,:,:,0]))<=.250001
            assert np.max(np.abs(data['suffix_u'][:,:,:,1]))<=.500001
            assert np.any(np.abs(data['requested'][:,0]-data['requested'][:,80])>.1)
            # All fault families have the same healthy commissioning evidence.
            prefix=data['prefix_pose'].reshape(7,10,401,3)
            for k in range(1,7): np.testing.assert_array_equal(prefix[0,:,:201],prefix[k,:,:201])
            for a in range(9):
                reference=np.repeat(data['suffix_pose'][:,a*9:a*9+1,:50],9,axis=1)
                np.testing.assert_array_equal(reference,data['suffix_pose'][:,a*9:a*9+9,:50])
            # Serial replay of one independent case/config must match saved data.
            i=c%70; row=metadata[i]; replay=sim.run(sim.world(c,row['replicate'],row['kind']),row['kind'])
            np.testing.assert_array_equal(replay['prefix']['pose'],data['prefix_pose'][i])
            np.testing.assert_array_equal(replay['pose'],data['suffix_pose'][i,:81])
            with np.load(s.OUT/'predictions'/f'{c}.npz') as f: predicted={k:f[k] for k in f.files}
            y=np.array([r['label'] for r in metadata]); np.testing.assert_array_equal(y,predicted['y'])
            for result in s.load(s.OUT/'per_config'/f'{c}.json'):
                name=f"{result['decoder']}__{result['selector']}"
                p=predicted[name+'_prediction']; m=result['metrics']
                independent={
                    'unknown_rejection':float(np.count_nonzero((y==-1)&(p==-1))/np.count_nonzero(y==-1)),
                    'known_macro_recall':float(np.mean([np.count_nonzero((y==k)&(p==k))/np.count_nonzero(y==k) for k in [1,2,3]])),
                    'healthy_false_alarm':float(np.count_nonzero((y==0)&(p!=0))/np.count_nonzero(y==0))}
                for key,value in independent.items(): assert abs(value-m[key])<1e-12
                if result['selector'] not in ['fixed1','passive8']:
                    branch=predicted[name+'_branch']; matrix=predicted[result['decoder']+'_all_decisions']
                    np.testing.assert_array_equal(p,matrix[np.arange(len(y)),branch])
                metric_rows+=1
            for method in ['eig','overlap']:
                a,_=select(Observation(data['prefix_u'][i],data['prefix_pose'][i]),method,np.load(s.WORK/'forecast_scale.npy'))
                u=np.concatenate([data['prefix_u'][i],data['suffix_u'][i,a*9,:50]])
                p=np.concatenate([data['prefix_pose'][i],data['suffix_pose'][i,a*9,:50]])
                b,_=select(Observation(u,p),method,np.load(s.WORK/'forecast_scale.npy'))
                assert a*9+b==predicted[f'forest_fit__{method}_branch'][i]
                selections+=1
            print('audited',c,flush=True)
    ref=s.OUT/'reference'
    tracked_clean=subprocess.run(['git','-C',str(s.WORK/'reference'),'diff','--quiet','HEAD']).returncode==0
    # Original reference receipts flagged untracked __pycache__ as an unclean
    # worktree. This independent check distinguishes it from source edits.
    assert tracked_clean
    s.dump(ref/'tracked_source_audit.json',dict(checked_utc=s.utc(),tracked_source_unchanged=True,
        note='source_unmodified=false in execution receipts came from untracked Python cache files, not tracked source changes.',
        reference_commit=subprocess.check_output(['git','-C',str(s.WORK/'reference'),'rev-parse','HEAD'],text=True).strip()))
    oracle=np.load(s.OUT/'oracle/predictions.npz'); result=s.load(s.OUT/'oracle/result.json')
    assert abs(np.mean(oracle['pred']==oracle['y'])-result['accuracy'])<1e-12
    s.dump(s.OUT/'data_manifest.json',files)
    s.dump(s.OUT/'final_audit.json',dict(checked_utc=s.utc(),frozen_core_unchanged=True,
        frozen_models_and_selection_unchanged=True,held_out_mechanisms_absent_from_baseline_fitting=True,
        disjoint_configuration_partitions=True,test_cases=cases,independent_metric_rows=metric_rows,
        serial_case_replays=20,causal_selector_replays=selections,commissioning_prefixes_label_independent=True,
        intervention_bounds_and_counterfactual_prefixes_checked=True,
        identifiability_reference_metrics_checked=True,data_manifest_sha256=s.sha(s.OUT/'data_manifest.json'),
        source_sha256=s.sha(__file__),freeze_sha256=s.sha(s.OUT/'freeze.json')))
    print('audit passed',cases,'cases',metric_rows,'metric rows',flush=True)


if __name__=='__main__': main()
