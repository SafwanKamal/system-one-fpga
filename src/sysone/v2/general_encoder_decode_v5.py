"""Schema-constrained, joint-span decoder; no gold values or benchmark rules."""
import math
from .general_tool_encoder import KINDS, scalar_from_span
from .general_tools import validate_value

CONSTANTS={'true':True,'false':False,'null':None,'empty_string':'','empty_array':[],'empty_object':{}}

def decode_argument(kind_scores, span_scores, offsets, sequences, lower, question, query, spec, required, constrained=True):
    valid=[i for i,s in enumerate(sequences) if s is not None and offsets[i][1]>offsets[i][0] and (s==1 or offsets[i][0]>=lower)]
    def span_value():
        if not valid:raise ValueError('no eligible value tokens')
        if not constrained:
            a=max(valid,key=lambda i:span_scores[i][0]);ends=[b for b in valid if a<=b<a+64 and sequences[b]==sequences[a]]
            b=max(ends,key=lambda i:span_scores[i][1])
            text=query if sequences[a]==1 else question
            return scalar_from_span(text[offsets[a][0]:offsets[b][1]],spec)
        pairs=sorted(((span_scores[a][0]+span_scores[b][1],a,b) for a in valid for b in valid if a<=b<a+64 and sequences[a]==sequences[b]),reverse=True)
        for _,a,b in pairs:
            text=query if sequences[a]==1 else question
            try:
                value=scalar_from_span(text[offsets[a][0]:offsets[b][1]],spec)
                validate_value(value,spec)
                return value
            except (ValueError,TypeError,KeyError):pass
        raise ValueError('no schema-compatible copy span')
    order=sorted(range(len(KINDS)),key=lambda i:kind_scores[i],reverse=True) if constrained else [max(range(len(KINDS)),key=lambda i:kind_scores[i])]
    for index in order:
        kind=KINDS[index]
        if kind=='unrepresentable':raise ValueError('unrepresentable argument')
        if kind=='omit':
            if required:
                if constrained:continue
                raise ValueError('missing required argument')
            return False,None
        try:
            value=span_value() if kind=='span' else CONSTANTS[kind]
            if constrained:validate_value(value,spec)
            return True,value
        except (ValueError,TypeError,KeyError):
            if not constrained:raise
    raise ValueError('no compatible argument kind')
