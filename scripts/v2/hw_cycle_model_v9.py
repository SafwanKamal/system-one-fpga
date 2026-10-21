"""Offline per-command cycle model for the Qwen HLS decoder (v8 baseline and v9 candidates).

Loop costs come from the v8 csynth report (II x trip count + iteration latency).
DDR terms use a measured efficiency: the full-vocabulary pass (cmd 4) streams
165MB at 3.78GB/s against a 4.0GB/s port, so weight streams run at ~0.945.
The model is validated against v8's measured command timings before any
projection is trusted. It is a planning tool, not a measurement.
"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
H,F,Q,KV,NL,NH,NK,VOCAB=1024,3072,2048,1024,28,16,8,151936
CLOCK=125e6
LAYER_BYTES=(Q*H+2*KV*H+H*Q+3*F*H)//32*34
VOCAB_BYTES=VOCAB*(H//32)*34
COLUMNS=[H,H,H,Q,H,H,F]           # matvec input widths, ops 0..6
QUANTIZED=[H,Q,H,F]               # ops whose inputs are requantized (1,2,5 reuse)
OUTPUTS=[Q,KV,KV,H,F,F,H]

PROFILES={
    # cycles per token-layer of serial vector work and per-position attention costs
    'v8':dict(stream_bytes_per_cycle=32,ports=1,efficiency=0.945,
              copy_in=sum(COLUMNS),quantize=sum(QUANTIZED)*76/32,copy_out=sum(OUTPUTS),
              rms=2*(3077+1031)+(NH+NK)*(389+135),silu=2*F,residual=2*2*H,rope=2*2057,append=518,
              kv_load_per_t=91,attend_per_t=131+3+32+8),
    # v9a terms from its csynth schedule: quantize 2x cols/4 + blocks, rms II=3 over
    # quads, rope/residual/append II=2 over quads, 8-wide attention (score 16/t,
    # max 1/t, exp 3/t, acc 16/t), head-major K+V bursts 32 beats/t at 256 bits.
    'v9a':dict(stream_bytes_per_cycle=32,ports=1,efficiency=0.945,
               copy_in=0,quantize=sum(QUANTIZED)*(2/4+1/32)+4*60,copy_out=sum(OUTPUTS)/4,
               rms=2*(774+263)+(NH+NK)*(102+39),silu=2*F,residual=2*517,rope=2*521,append=517,
               kv_load_per_t=32,attend_per_t=16+1+3+16,attend_fixed=32+4*40),
    # v9b projection: v9a vector path plus a second 128-bit HP port for weights.
    'v9b':dict(stream_bytes_per_cycle=64,ports=2,efficiency=0.90,
               copy_in=0,quantize=sum(QUANTIZED)*(2/4+1/32)+4*60,copy_out=sum(OUTPUTS)/4,
               rms=2*(774+263)+(NH+NK)*(102+39),silu=2*F,residual=2*517,rope=2*521,append=517,
               kv_load_per_t=32,attend_per_t=16+1+3+16,attend_fixed=32+4*40),
}
COMMAND_OVERHEAD_S=60e-6           # ARM MMIO setup + 50us completion polling granularity


def matrix_cycles(p,bytes_):
    return bytes_/(p['stream_bytes_per_cycle']*p['efficiency'])


def per_token(p):
    return sum(p[k] for k in ['copy_in','quantize','copy_out','rms','silu','residual','rope','append'])


def layer_cycles(p,first,batch):
    """One decoder-layer command over tokens first..first+batch-1."""
    total=first+batch
    rows=lambda b:max(first+b+1,16) if 'attend_fixed' in p else first+b+1
    attention=NK*(p['kv_load_per_t']*total+sum(p['attend_per_t']*rows(b)+p.get('attend_fixed',0) for b in range(batch)))
    return matrix_cycles(p,LAYER_BYTES)+batch*per_token(p)+attention


def run(p,prompt=62,generated=16,batch=8):
    prefill=0.0;position=0
    while position<prompt:
        n=min(batch,prompt-position)
        prefill+=NL*(layer_cycles(p,position,n)/CLOCK+COMMAND_OVERHEAD_S);position+=n
    decode=0.0
    for step in range(generated-1):
        decode+=NL*(layer_cycles(p,prompt+step,1)/CLOCK+COMMAND_OVERHEAD_S)
    vocab=generated*(matrix_cycles(p,VOCAB_BYTES)/CLOCK+19*COMMAND_OVERHEAD_S)
    return dict(prefill_cmd8_s=prefill,decode_cmd2_s=decode,vocab_cmd4_s=vocab)


def main():
    measured=json.loads((ROOT/'build/v2/qwen-fpga-decoder-v8/real-command-result.json').read_text())
    timing=measured['command_timing']
    observed=dict(prefill_cmd8_s=timing['8']['seconds'],decode_cmd2_s=timing['2']['seconds'],
                  vocab_cmd4_s=timing['4']['seconds'])
    fixed=measured['elapsed_seconds']-sum(observed.values())
    out=dict(observed_v8=observed,non_kernel_seconds=fixed,profiles={})
    for name,p in PROFILES.items():
        m=run(p);m['end_to_end_s']=sum(m.values())+fixed
        if name=='v8':
            m['model_error_percent']={k:100*(m[k]-observed[k])/observed[k] for k in observed}
        out['profiles'][name]=m
    long=dict()
    for name,p in PROFILES.items():
        long[name]=dict(decode_layer_ms_at_255=layer_cycles(p,255,1)/CLOCK*1e3,
                        attention_share_at_255=NK*(p['kv_load_per_t']*256+p['attend_per_t']*256+p.get('attend_fixed',0))/layer_cycles(p,255,1))
    out['context_255']=long
    print(json.dumps(out,indent=2))
    v8=out['profiles']['v8']['model_error_percent']
    if any(abs(e)>15 for e in v8.values()):
        print('MODEL NOT VALIDATED: v8 error exceeds 15%',file=sys.stderr);sys.exit(1)


if __name__=='__main__':main()
