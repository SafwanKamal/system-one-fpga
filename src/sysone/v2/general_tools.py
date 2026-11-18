"""General tool-call proposal parsing and bounded structural validation.

No tool execution. BFCL semantic matching remains separate from structural typing.
"""
from __future__ import annotations
import copy
import json
import math
import re

TYPE_NAMES={'str':'string','int':'integer','float':'number','bool':'boolean',
            'list':'array','tuple':'array','dict':'object'}


def normalize_schema(spec):
    spec=copy.deepcopy(spec)
    typ=spec.get('type')
    if isinstance(typ,str):
        spec['type']=TYPE_NAMES.get(typ,typ)
    if 'properties' in spec:
        spec['properties']={k:normalize_schema(v) for k,v in spec['properties'].items()}
    if isinstance(spec.get('items'),dict):
        spec['items']=normalize_schema(spec['items'])
    return spec


def normalize_tool(source):
    tool=copy.deepcopy(source)
    params=tool.get('parameters',{})
    # xLAM stores parameter definitions directly; BFCL stores JSON-style properties.
    if not isinstance(params.get('type'),str) or 'properties' not in params:
        required=[k for k,v in params.items() if v.get('required',False)]
        params=dict(type='object',properties=params,required=required)
    else:
        params.setdefault('required',[])
    params=normalize_schema(params)
    for spec in params.get('properties',{}).values():
        spec.setdefault('description','')
    tool['parameters']=params
    tool.setdefault('description','')
    return tool


def validate_value(value,spec,depth=0):
    if depth>4:
        raise ValueError('argument depth exceeds 4')
    if isinstance(value,str) and len(value)>512:
        raise ValueError('string exceeds 512 characters')
    if isinstance(value,(dict,list)) and len(value)>32:
        raise ValueError('collection exceeds 32 elements')
    typ=TYPE_NAMES.get(spec.get('type'),spec.get('type'))
    if value is None:
        if spec.get('nullable') or typ in ('null','any'):
            return
        raise ValueError('unexpected null')
    if typ=='string' and type(value) is not str:
        raise ValueError('expected string')
    if typ=='integer' and type(value) is not int:
        raise ValueError('expected integer')
    if typ in ('number','float') and (type(value) not in (int,float) or not math.isfinite(value)):
        raise ValueError('expected finite number')
    if typ=='boolean' and type(value) is not bool:
        raise ValueError('expected boolean')
    if typ=='array':
        if type(value) is not list:
            raise ValueError('expected array')
        for x in value:
            validate_value(x,spec.get('items',{'type':'any'}),depth+1)
    if typ=='object':
        if type(value) is not dict:
            raise ValueError('expected object')
        props=spec.get('properties')
        if props is not None:
            if set(value)-set(props):
                raise ValueError('unknown argument')
            if set(spec.get('required',[]))-set(value):
                raise ValueError('missing required argument')
            for k,v in value.items():
                validate_value(v,props[k],depth+1)
        else:
            for v in value.values():
                validate_value(v,{'type':'any'},depth+1)
    if typ=='any':
        if type(value) not in (str,int,float,bool,list,dict):
            raise ValueError('unsupported JSON value')
        if type(value) is float and not math.isfinite(value):
            raise ValueError('nonfinite value')
        if isinstance(value,(list,dict)):
            for x in value.values() if isinstance(value,dict) else value:
                validate_value(x,{'type':'any'},depth+1)
    elif typ not in ('string','integer','number','float','boolean','array','object'):
        raise ValueError('unsupported schema type')
    if 'enum' in spec and not any(type(value) is type(x) and value==x for x in spec['enum']):
        raise ValueError('value outside enum')


def validate_calls(calls,tools):
    if type(calls) is not list or len(calls)>4:
        raise ValueError('at most four calls')
    by_name={t['name']:normalize_tool(t) for t in tools}
    if len(by_name)!=len(tools):
        raise ValueError('duplicate tool names')
    for call in calls:
        if type(call) is not dict or set(call)!= {'name','arguments'}:
            raise ValueError('incorrect call fields')
        if call['name'] not in by_name:
            raise ValueError('unknown tool')
        validate_value(call['arguments'],by_name[call['name']]['parameters'])
    return calls


class CallParser:
    def __init__(self,text):
        if len(text.encode())>8192:
            raise ValueError('output exceeds 8192 bytes')
        self.text=text
        self.i=0

    def skip(self):
        while self.i<len(self.text) and self.text[self.i].isspace():
            self.i+=1

    def take(self,literal):
        self.skip()
        if not self.text.startswith(literal,self.i):
            raise ValueError('unexpected call syntax')
        self.i+=len(literal)

    def value(self,depth=0):
        self.skip()
        if depth>4:
            raise ValueError('value nesting exceeds profile')
        if self.text.startswith('<escape>',self.i):
            self.take('<escape>')
            end=self.text.find('<escape>',self.i)
            if end<0:
                raise ValueError('unterminated string')
            value=self.text[self.i:end]
            if len(value)>512:
                raise ValueError('string too long')
            self.i=end+len('<escape>')
            return value
        if self.text.startswith('{',self.i):
            self.take('{');result={}
            if self.text.startswith('}',self.i):
                self.take('}');return result
            while True:
                self.skip()
                if self.text.startswith('<escape>',self.i):
                    key=self.value(depth+1)
                else:
                    match=re.match(r'[A-Za-z_][A-Za-z0-9_.-]*',self.text[self.i:])
                    if not match:
                        raise ValueError('invalid key')
                    key=match.group();self.i+=len(key)
                if key in result:
                    raise ValueError('duplicate argument')
                self.take(':');result[key]=self.value(depth+1);self.skip()
                if len(result)>32:
                    raise ValueError('too many object fields')
                if self.text.startswith('}',self.i):
                    self.take('}');return result
                self.take(',')
        if self.text.startswith('[',self.i):
            self.take('[');result=[]
            if self.text.startswith(']',self.i):
                self.take(']');return result
            while True:
                result.append(self.value(depth+1));self.skip()
                if len(result)>32:
                    raise ValueError('too many array elements')
                if self.text.startswith(']',self.i):
                    self.take(']');return result
                self.take(',')
        match=re.match(r'(true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)',self.text[self.i:])
        if not match:
            raise ValueError('invalid scalar')
        self.i+=len(match.group())
        value=json.loads(match.group())
        if type(value) is float and not math.isfinite(value):
            raise ValueError('nonfinite number')
        return value


def parse_functiongemma(raw,tools):
    parser=CallParser(raw.strip())
    calls=[]
    while parser.text.startswith('<start_function_call>',parser.i):
        parser.take('<start_function_call>call:')
        parser.skip()
        match=re.match(r'[A-Za-z_][A-Za-z0-9_.-]*',parser.text[parser.i:])
        if not match:
            raise ValueError('invalid tool name')
        name=match.group();parser.i+=len(name)
        arguments=parser.value()
        parser.take('<end_function_call>')
        calls.append(dict(name=name,arguments=arguments))
        parser.skip()
        if len(calls)>4:
            raise ValueError('too many calls')
    suffix=parser.text[parser.i:].strip()
    if calls:
        if suffix not in ('','<start_function_response>','<end_of_turn>','<eos>'):
            raise ValueError('trailing text or incomplete call')
    elif '<start_function_call>' in suffix or '<end_function_call>' in suffix:
        raise ValueError('malformed call markers')
    # No-call text is a nonactionable reject; it is wrong on supported calls.
    return validate_calls(calls,tools)


def canonical_outcome(calls):
    return dict(outcome='Accepted',calls=calls) if calls else dict(outcome='Reject',reason='no_tool_call')
