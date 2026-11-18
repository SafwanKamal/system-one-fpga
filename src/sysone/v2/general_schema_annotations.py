"""Conservative xLAM annotation adapter; no evaluation of Python expressions.

Optional argument markers mean omission is allowed, not that null is a value.
Unknown annotations remain unsupported by the existing bounded validator.
"""
import ast
import copy
import re
from .general_tools import normalize_tool


SCALARS = {'str': 'string', 'int': 'integer', 'float': 'number',
           'bool': 'boolean', 'list': 'array', 'List': 'array',
           'dict': 'object', 'Dict': 'object', 'tuple': 'array', 'Tuple': 'array'}


def annotation_schema(text):
    # Strip only documented annotation suffix syntax; never infer a default.
    text = re.sub(r",\s*(?:optional|default\s*=.*)$", '', text.strip())
    def convert(node, depth=0):
        if depth > 4:
            raise ValueError('annotation depth')
        if isinstance(node, ast.Name):
            name = node.id
            if name not in SCALARS and name not in ('string', 'integer', 'number', 'boolean', 'array', 'object', 'any', 'null'):
                raise ValueError('unknown annotation')
            return {'type': SCALARS.get(name, name)}
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            name = node.value.id
            parts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if name in ('List', 'list') and len(parts) == 1:
                return {'type': 'array', 'items': convert(parts[0], depth+1)}
            if name in ('Tuple', 'tuple'):
                # Positional heterogeneous tuples need a different validator.
                converted = [convert(p, depth+1) for p in parts]
                if converted and all(p == converted[0] for p in converted):
                    return {'type': 'array', 'items': converted[0],
                            'minItems': len(parts), 'maxItems': len(parts)}
                raise ValueError('heterogeneous tuple')
        raise ValueError('unsupported annotation')
    try:
        result = convert(ast.parse(text, mode='eval').body)
        # Existing validator does not enforce tuple lengths: retain unsupported
        # tuples rather than weakening the declared type.
        if 'minItems' in str(result):
            return None
        return result
    except (ValueError, SyntaxError, RecursionError):
        return None


def adapt_tool(tool):
    tool = normalize_tool(tool)
    def adapt(spec):
        spec = copy.deepcopy(spec)
        typ = spec.get('type')
        if isinstance(typ, str):
            parsed = annotation_schema(typ)
            if parsed is not None:
                # An explicit JSON schema item declaration takes precedence.
                for key, value in parsed.items():
                    if key == 'type' or key not in spec:
                        spec[key] = value
        if 'properties' in spec:
            spec['properties'] = {k: adapt(v) for k,v in spec['properties'].items()}
        if isinstance(spec.get('items'), dict):
            spec['items'] = adapt(spec['items'])
        return spec
    tool['parameters'] = adapt(tool['parameters'])
    return tool


def adapt_records(rows):
    return [{**r, 'tools': [adapt_tool(t) for t in r['tools']]} for r in rows]
