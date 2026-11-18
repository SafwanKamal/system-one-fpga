"""Shared local adapter to pinned BFCL Python checker functions."""
import copy
import json
from pathlib import Path
import random
import sys


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]


def select_cases(path,per_category=5):
    groups={}
    for row in read_jsonl(path):
        groups.setdefault(row['category'],[]).append(row)
    rng=random.Random(20261017)
    result=[]
    for name,rows in sorted(groups.items()):
        rng.shuffle(rows)
        result.extend(rows[:per_category] if per_category else rows)
    return result


class BFCLPythonChecker:
    def __init__(self,root):
        sys.path.insert(0,str(Path(root).resolve()))
        from bfcl_eval.constants.enums import Language
        from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker,simple_function_checker
        self.language=Language.PYTHON
        self.check=ast_checker
        self.check_single=simple_function_checker

    def score(self,case,calls,gold):
        if case['category']=='irrelevance':
            return dict(valid=not calls,error=[] if not calls else ['Expected no calls'])
        return self.check(copy.deepcopy(case['tools']),[{c['name']:c['arguments']} for c in calls],
                          copy.deepcopy(gold),self.language,case['category'],'sysone_local')

    def arguments(self,case,calls,gold):
        """Diagnostic argument micro score, pairing same-name calls greedily.

        Full-command scoring above uses upstream call-set matching. This metric
        never changes that decision and is explicitly a diagnostic for repeated APIs.
        """
        if case['category']=='irrelevance':
            return dict(tp=0,fp=sum(len(c['arguments']) for c in calls),fn=0)
        expected=[(name,args) for answer in gold for name,args in answer.items()]
        remaining=list(range(len(expected)))
        counts=dict(tp=0,fp=0,fn=0)
        specs={x['name']:x for x in case['tools']}
        for call in calls:
            choices=[]
            for i in remaining:
                name,args=expected[i]
                if name!=call['name']:
                    continue
                tp=0
                for key,value in call['arguments'].items():
                    if key not in args:
                        continue
                    spec=copy.deepcopy(specs[name])
                    spec['parameters']['required']=[key]
                    answer={name:{key:args[key]}}
                    check=self.check_single(spec,{name:{key:value}},answer,self.language,'sysone_local')
                    tp+=bool(check['valid'])
                needed=sum('' not in values for values in args.values())
                # Optional arguments omitted by the model are not missing.
                missing=sum(key not in call['arguments'] and '' not in values for key,values in args.items())
                wrong=sum(key in call['arguments'] for key in args)-tp
                choices.append((tp,i,missing+wrong))
            if not choices:
                counts['fp']+=len(call['arguments'])
                continue
            tp,i,fn=max(choices)
            remaining.remove(i)
            counts['tp']+=tp
            counts['fp']+=len(call['arguments'])-tp
            counts['fn']+=fn
        for i in remaining:
            counts['fn']+=sum('' not in values for values in expected[i][1].values())
        return counts


def checker_self_check(root,cases,answers):
    checker=BFCLPythonChecker(root)
    case=next(x for x in cases if x['id']=='simple_python_0')
    calls=[dict(name='calculate_triangle_area',arguments=dict(base=10,height=5))]
    assert checker.score(case,calls,answers[case['id']])['valid']
    calls[0]['arguments']['base']=11
    assert not checker.score(case,calls,answers[case['id']])['valid']
    return checker
