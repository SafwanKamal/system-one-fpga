"""Input-ID boundary for the proposed text-only 32-bit token ABI."""
from numbers import Integral


def validate_prompt_ids(ids,vocab_size=262144,context=2048,output_reserve=256):
    if not 0<output_reserve<context or vocab_size<=0:
        raise ValueError('invalid profile')
    if not ids or len(ids)+output_reserve>context:
        raise ValueError('prompt/output context profile')
    for value in ids:
        if isinstance(value,bool) or not isinstance(value,Integral) or not 0<=int(value)<vocab_size:
            raise ValueError('token ID outside text model embedding range')
    return True
