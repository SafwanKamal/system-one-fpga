"""Isolated future template candidate; never changes the cached official file.

Repairs property names confused with schema metadata and JSON null targets.
This does not claim lossless rendering of every JSON Schema constraint.
Not activated in the fixed v5 checkpoint-interpolation experiment.
"""
import hashlib

OFFICIAL_SHA256='db61fb01017bd82401d3ffca4f8e066cd56ff6d38d2a30c4058770c0bf7ab49b'


def faithful_parameter_template(original):
    if hashlib.sha256(original.encode('utf-8')).hexdigest()!=OFFICIAL_SHA256:
        raise ValueError('unqualified parent template bytes')
    replacements=[
        ('macro format_parameters(properties, required)', 'macro format_parameters(properties, required, schema_mapping=false)'),
        ('{%- if key not in standard_keys -%}', '{%- if not schema_mapping or key not in standard_keys -%}'),
        ("format_parameters(value, value['required'] | default([]))", "format_parameters(value, value['required'] | default([]), schema_mapping=true)"),
    ]
    for old,new in replacements:
        if original.count(old)!=1:raise ValueError('expected unique template repair location')
        original=original.replace(old,new,1)
    return original


def faithful_template(original):
    original=faithful_parameter_template(original)
    replacements=[
        ("{%- else -%}\n    {{- argument -}}\n{%- endif -%}\n{%- endmacro -%}",
         "{%- elif argument is none -%}\n    {{- 'null' -}}\n{%- else -%}\n    {{- argument -}}\n{%- endif -%}\n{%- endmacro -%}"),
    ]
    for old,new in replacements:
        if original.count(old)!=1:raise ValueError('expected unique template repair location')
        original=original.replace(old,new,1)
    return original
