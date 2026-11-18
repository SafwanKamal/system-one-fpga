"""Create the separately instrumented service; preserve all sealed originals."""
from pathlib import Path
import difflib,hashlib,json
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=ROOT/'firmware/typed200_trace'
    dest=out/'service.c'
    if dest.exists():raise ValueError('Preserve existing candidate')
    original=ROOT/'firmware/typed200_r5/service.c'
    s=original.read_text();before=s
    def change(old,new):
        nonlocal s
        if s.count(old)!=1:raise ValueError('Unexpected frozen source anchor: '+old)
        s=s.replace(old,new)
    change('#include "service.h"','#include "trace.h"')
    change('fence();c->shared->command_state=TY_CMD_DONE;',
           'ty_trace_shared(c,origin);\n    fence();c->shared->command_state=TY_CMD_DONE;\n    ty_trace_event(c,TR_SHARED_DONE);')
    change('r.outcome=TI_INVALID;\n    output(c,&r,0);',
           'r.outcome=TI_INVALID;\n    output(c,&r,0);ty_trace_finish(c);')
    change('c->phase=TY_HALTED;output(c,&r,0);', 'c->phase=TY_HALTED;output(c,&r,0);ty_trace_finish(c);')
    # INIT logging occurs after original identity initialization succeeds: never
    # read uninitialized context fields on rejected startup.
    change('if(!ti_bridge_init(&c->bridge,c->identity.session))return 0;',
           'if(!ti_bridge_init(&c->bridge,c->identity.session))return 0;\n    ty_trace_reset();ty_trace_event(c,TR_INIT);')
    change('if(!ti200_terminal_observe(c->mmio,&r))return 0;',
           'if(!ti200_terminal_observe(c->mmio,&r))return 0;\n    ty_trace_event(c,TR_TERMINAL_OBSERVED);ty_trace_pl(c);')
    change('if(c->phase==TY_IDLE){fence();c->mmio[0]=8;fence();}',
           'if(c->phase==TY_IDLE){fence();c->mmio[0]=8;fence();ty_trace_event(c,TR_ACK_WRITTEN);}\n    ty_trace_finish(c);')
    change('c->shared->boot_status=1;', 'c->shared->boot_status=1;ty_trace_event(c,TR_BOOT_READY);')
    change('c->phase=TY_ADMISSION;return;', 'c->phase=TY_ADMISSION;ty_trace_event(c,TR_START_SUBMITTED);return;')
    change('if(ti_bridge_admitted(&c->bridge,&c->identity))c->phase=TY_CORE;',
           'if(ti_bridge_admitted(&c->bridge,&c->identity)){c->phase=TY_CORE;ty_trace_event(c,TR_ADMISSION_OBSERVED);}')
    change('int success=(native&31)==30;', 'ty_trace_event(c,TR_NATIVE_OBSERVED);\n        int success=(native&31)==30;')
    change('if(success && !ti200_copy_hidden(c->mmio,c->hidden,c->input))success=0;',
           'if(success){ty_trace_event(c,TR_COPY_BEGIN);\n            if(!ti200_copy_hidden(c->mmio,c->hidden,c->input))success=0;\n            ty_trace_event(c,TR_COPY_END);}')
    change('if(ti_bridge_core(&c->bridge,1,success,(native&2)!=0,c->input,&c->proposal)) {',
           'ty_trace_event(c,TR_HEAD_BEGIN);\n        int proposal_ready=ti_bridge_core(&c->bridge,1,success,(native&2)!=0,c->input,&c->proposal);\n        ty_trace_event(c,TR_HEAD_END);\n        if(proposal_ready) {')
    change('ti200_propose(c->mmio,&c->proposal);c->phase=TY_TERMINAL;',
           'ty_trace_event(c,TR_PROPOSAL_BEGIN);\n            ti200_propose(c->mmio,&c->proposal);c->phase=TY_TERMINAL;\n            ty_trace_event(c,TR_PROPOSAL_END);')
    dest.write_text(s)
    (out/'service.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),
        fromfile='frozen/service.c',tofile='trace/service.c')))
    (out/'candidate.json').write_text(json.dumps({'base_service_sha256':sha(original),
        'candidate_service_sha256':sha(dest),'scope':'Owner-local one-shot diagnostic trace; not deployed',
        'default_clock':'none; ordered events only','target_executed':False,
        'limits':['Instrumentation adds instructions and pre-ACK read latency',
                  'No equal target timing/WCET claim','No raw-CSR snapshot coherence proof']},indent=2)+'\n')
    print('Created separate trace service; original unchanged')
if __name__=='__main__':main()
