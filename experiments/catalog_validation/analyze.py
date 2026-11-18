"""Cluster-level summaries and a standalone scientific figure."""
import numpy as np
import study as s


def main():
    s.verify_freeze(); rows=s.load(s.OUT/'summary.json')
    prediction={}
    for c in s.CONFIGS['test']:
        with np.load(s.OUT/'predictions'/f'{c}.npz') as f: prediction[c]={k:f[k] for k in f.files}
    rng=np.random.default_rng(s.SEED); pairs=[]
    for left,right in [('fixed','passive8'),('fixed','passive10'),('eig','fixed'),('action_oracle','fixed')]:
        deltas=[]
        for c,a in prediction.items():
            take=a['y']==-1
            deltas.append(float(np.mean(a[f'forest_fit__{left}_prediction'][take]==-1)-
                                np.mean(a[f'forest_fit__{right}_prediction'][take]==-1)))
        boot=np.array(deltas)[rng.integers(0,20,(20000,20))].mean(1)
        pairs.append(dict(decoder='forest_fit',left=left,right=right,delta=float(np.mean(deltas)),
                          cluster_bootstrap_ci95=np.quantile(boot,[.025,.975]).tolist(),configuration_deltas=deltas))
    family=[]; calibration=[]
    for row in rows:
        decoder,selector=row['decoder'],row['selector']; name=f'{decoder}__{selector}'
        all_y=np.concatenate([a['y'] for a in prediction.values()]); all_kind=np.concatenate([a['kind'] for a in prediction.values()])
        pred=np.concatenate([a[name+'_prediction'] for a in prediction.values()])
        proba=np.concatenate([a[name+'_proba'] for a in prediction.values()])
        by_family={k:float(np.mean(pred[all_kind==k]==-1)) for k in s.sim.KINDS[4:]}
        family.append(dict(decoder=decoder,selector=selector,unknown_rejection_by_family=by_family,
                           unknown_false_named_fault=float(np.mean(pred[all_y==-1]>0)),
                           unknown_false_healthy=float(np.mean(pred[all_y==-1]==0))))
        known=all_y>=0; onehot=np.eye(4)[all_y[known]]
        confidence=proba[known].max(1); correct=proba[known].argmax(1)==all_y[known]
        ece=0.
        for low in np.linspace(0,.9,10):
            take=(confidence>=low)&(confidence<=low+.1 if low>.89 else confidence<low+.1)
            if take.any(): ece+=float(take.mean()*abs(correct[take].mean()-confidence[take].mean()))
        calibration.append(dict(decoder=decoder,selector=selector,known_only_brier=float(np.mean(np.sum((proba[known]-onehot)**2,1))),
                                known_only_ece=ece,note='Not calibrated probabilities of an unknown mechanism.'))
    s.dump(s.OUT/'paired_comparisons.json',pairs); s.dump(s.OUT/'by_mechanism.json',family)
    s.dump(s.OUT/'calibration.json',calibration)
    fixed_curves=[]
    for decoder in s.DECODERS:
        curves=[s.load(s.OUT/'per_config'/f'{c}_{decoder}_fixed_curves.json') for c in s.CONFIGS['test']]
        for branch in range(81):
            metrics={k:float(np.mean([cc[branch][k] for cc in curves])) for k in [
                'unknown_rejection','known_macro_recall','healthy_false_alarm']}
            fixed_curves.append(dict(decoder=decoder,branch=branch,metrics=metrics,
                feasible=metrics['known_macro_recall']>=.9 and metrics['healthy_false_alarm']<=.05,
                status='Hindsight descriptive curve; never selected for deployment.'))
    s.dump(s.OUT/'hindsight_fixed_curves.json',fixed_curves)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    shown=['passive8','passive10','fixed','eig','overlap','action_oracle']
    data=[next(r for r in rows if r['decoder']=='forest_fit' and r['selector']==p) for p in shown]
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    x=np.arange(len(data)); colors=['lightgray','gray','tab:blue','tab:orange','tab:green','tab:red']
    axes[0].bar(x,[r['metrics']['unknown_rejection'] for r in data],color=colors)
    axes[0].set(xticks=x,xticklabels=['Passive\n8 s, held','Passive\n10 s','Optimized\nfixed','Information\ngain','Output-box\noverlap','Label-informed\nceiling'],
                ylim=(0,1),ylabel='Unknown-fault rejection',title='Same compact classifier + absolute-fit rejection')
    for i,r in enumerate(data): axes[0].text(i,r['metrics']['unknown_rejection']+.025,f"{r['metrics']['unknown_rejection']:.1%}",ha='center',fontsize=9)
    axes[0].tick_params(axis='x', labelsize=8)
    for p,color in [('passive10','gray'),('fixed','tab:blue'),('eig','tab:orange'),('action_oracle','tab:red')]:
        r=next(r for r in family if r['decoder']=='forest_fit' and r['selector']==p)
        axes[1].plot(range(3),list(r['unknown_rejection_by_family'].values()),'o-',label=p,color=color)
    axes[1].set(xticks=range(3),xticklabels=['Actuator lag','Dead zone','Sensor latency'],ylim=(0,1.04),ylabel='Unknown-fault rejection',title='600 unknown cases across 20 configurations')
    axes[1].legend(fontsize=8); axes[1].grid(alpha=.2)
    fig.suptitle('Synthetic diagnostic probes: fixed tests help; adaptive baselines do not beat them')
    fig.savefig(s.OUT/'probe_comparison.png',dpi=180); plt.close(fig)
    print(pairs)


if __name__=='__main__': main()
