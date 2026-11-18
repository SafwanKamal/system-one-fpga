"""Derive a new runner with independent frozen parent arithmetic on reference side."""
from create_typed200_clamp_candidate import ROOT, verify

def main():
    verify()
    parent=ROOT/'simulation/v2/run_typed200_profile_cache.sh'
    dest=ROOT/'simulation/v2/run_typed200_clamp.sh'
    assert not dest.exists()
    s=parent.read_text().replace('typed200-profile-cache-integration-v1','typed200-clamp-integration-v1')
    s=s.replace('candidates/typed200_profile_cache','candidates/typed200_clamp')
    anchor="r=r.replace('result_streamer #(','reference_result_streamer #(',1)"
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+"\nr=r.replace('encoder_layer #(','reference_encoder_layer #(',1)")
    anchor="p=sim/'kr260_encoder_tb.sv';s=p.read_text()"
    assert s.count(anchor)==1
    extra='''# Independent arithmetic/control reference: do not share changed ADD_SKIP.
r=(repo/'rtl/v2/candidates/typed200_profile_cache/encoder/encoder_layer.sv').read_text()
r=re.sub(r'\\bmodule\\s+encoder_layer\\b','module reference_encoder_layer',r,count=1)
r=r.replace('add_skip_engine #(','reference_add_skip_engine #(',1)
(sim/'reference_encoder_layer.sv').write_text(r)
r=(repo/'rtl/v2/candidates/typed200_profile_cache/encoder/add_skip_engine.sv').read_text()
r=re.sub(r'\\bmodule\\s+add_skip_engine\\b','module reference_add_skip_engine',r,count=1)
(sim/'reference_add_skip_engine.sv').write_text(r)
'''
    s=s.replace(anchor,extra+anchor)
    anchor='reference_encoder_system.sv reference_result_streamer.sv'
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+' reference_encoder_layer.sv reference_add_skip_engine.sv')
    with dest.open('w',encoding='utf-8',newline='\n') as f:f.write(s)
    print('PASS new regression runner with separately renamed frozen parent ADD_SKIP and encoder_layer')

if __name__=='__main__':main()
