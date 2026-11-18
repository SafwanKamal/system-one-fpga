"""Fresh component-separated development and conservative model selection.

This is development evidence, never a blind or external benchmark.
"""
import torch


def interpolate(official,trained,alpha):
    if alpha not in (0.0,0.25,1.0) or official.keys()!=trained.keys():
        raise ValueError('undeclared interpolation or keys differ')
    result={}
    for name,left in official.items():
        right=trained[name]
        if left.dtype!=torch.float32 or right.dtype!=left.dtype or left.shape!=right.shape:
            raise ValueError('interpolation shape/dtype differs')
        if not torch.isfinite(left).all() or not torch.isfinite(right).all():
            raise ValueError('nonfinite interpolation input')
        result[name]=left.clone() if alpha==0 else right.clone() if alpha==1 else left+alpha*(right-left)
        if not torch.isfinite(result[name]).all():raise ValueError('nonfinite interpolation output')
    return result


def improves(candidate, incumbent):
    """No sacrifice in correct accepted calls or empirical accepted precision."""
    if candidate['correct']<=incumbent['correct']:
        return False
    if candidate['correct_accepted']<incumbent['correct_accepted']:
        return False
    # An incumbent accepting nothing has no observed errors to exceed.
    if not incumbent['accepted']:
        return candidate['wrong_accepted']==0
    if not candidate['accepted']:
        return True
    return (candidate['wrong_accepted']*incumbent['accepted']
            <=incumbent['wrong_accepted']*candidate['accepted'])
