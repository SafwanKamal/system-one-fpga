"""Fresh development revision for the verified 1024-token candidate context."""
import copy
import json
from .baselines import ASSET_RE
from .dataset import make_case, STRATA, public_input, SYSTEM
from .schema import canonical, encode
from ..v8_benchmark import chat

VERSION='maintenance-pilot-v2-context1024'
CONTEXT=1024
OUTPUT=256


def mention_order(public):
    """Order public candidates by mentions, without choosing/filling any field."""
    catalog=public['catalog']
    mentions=ASSET_RE.findall(public['request'])+ASSET_RE.findall(public['context'].get('previous_request',''))
    ordered=[]
    for asset in mentions+catalog:
        asset=asset.upper()
        if asset in catalog and asset not in ordered:ordered.append(asset)
    return ordered


def _replace(value,mapping):
    if isinstance(value,dict):return {k:_replace(v,mapping) for k,v in value.items()}
    if isinstance(value,list):return [_replace(v,mapping) for v in value]
    if isinstance(value,str):
        return ASSET_RE.sub(lambda m:mapping.get(m[0],m[0]),value)
    return value


def corpus():
    result={}
    for split,count,start in (('train',120,21),('tuning',20,31),('audit',20,41)):
        rows=[]
        for category in STRATA:
            for i in range(count):
                # New seeds/values; old cases and outputs are never rewritten.
                case=make_case(split,category,2000+i)
                mapping={old:f'{kind}{n}' for kind in 'PMF' for old,n in
                         zip([a for a in case['catalog'] if a.startswith(kind)],range(start,start+4))}
                case=_replace(case,mapping)
                case['id']=f'v2-{split}-{category}-{i:03d}'
                case['template_family']=f'v2/{split}/{category}/{i%24}'
                case['semantic_signature']=canonical(case['gold'])
                case['catalog']=mention_order(public_input(case))
                rows.append(case)
        result[split]=rows
    return result


def demonstrations(train):
    predicates=[
        lambda c:c['stratum']=='direct' and c['gold']['outcome']=='plan' and c['gold']['steps'][0]['tool']=='read_metric',
        lambda c:c['stratum']=='conditional' and len(c['gold']['steps'])==3,
        lambda c:c['stratum']=='clarification' and c['gold']['reason']=='missing_reference',
        lambda c:c['stratum']=='unsupported' and c['gold']['reason']=='unsupported_operation',
    ]
    return [copy.deepcopy(next(c for c in train if pred(c))) for pred in predicates]


# Keep the full tool/argument semantics, but show genuinely valid JSON examples.
SYSTEM_V2=SYSTEM+' Use the exact outer outcome array. A node is ["tool","asset",{arguments},false] or true for a guarded node. Never emit a standalone object or invent extra nodes.'


def prompt(case,demos=()):
    history=[]
    for example in demos:
        # Examples illustrate the fixed codec, not a filtered catalog for the query.
        history.extend([('user',example['request']),
                        ('assistant',encode(example['gold']))])
    return chat(SYSTEM_V2,json.dumps(public_input(case),separators=(',',':')),history)


def calibration_subset(rows):
    """Four unique public inputs per stratum; no selection by predictions/gold correctness."""
    selected=[]
    for stratum in STRATA:
        seen=set()
        for case in rows:
            key=json.dumps(public_input(case),sort_keys=True)
            if case['stratum']==stratum and key not in seen:
                selected.append(case);seen.add(key)
            if len(seen)==4:break
        if len(seen)!=4:raise ValueError('Insufficient tuning diversity')
    return selected
