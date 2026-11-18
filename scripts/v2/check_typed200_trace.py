"""Build/test the separate trace firmware and link a diagnostic R5 ELF locally."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.typed200_capture import ExpectedCapture
from sysone.v2.typed200_trace import assess_trace
from audit_typed200_trace import audit
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args()
    import re
    if not re.fullmatch(r'typed200-trace-host-v[0-9]+',a.name):raise ValueError('Distinct trace run name required')
    seal=ROOT/'docs/research/2026-10-15-typed200-capture-validation.json'
    old=json.loads(seal.read_text());preserved={}
    for k in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256'):
        for p,h in old[k].items():
            if sha(ROOT/p)!=h:raise ValueError('Changed sealed file: '+p)
            preserved[p]=h
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    commands=[]
    def run(cmd,log,env=None):
        p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/log).write_bytes(p.stdout);commands.append({'argv':cmd,'returncode':p.returncode,'log':log})
        if p.returncode:raise RuntimeError('Failed '+log+'; attempt preserved')
    # Reuse the frozen host harness, adding export assertions only in this copy.
    source=(ROOT/'firmware/typed200_qualification/capture_host.c').read_text()
    source=source.replace('#include "abi_layout.c"','#include "firmware/typed200_qualification/abi_layout.c"\n#include "firmware/typed200_trace/trace.h"')
    source=source.replace('#include "../typed200_r5/test_service.c"','#include "firmware/typed200_r5/test_service.c"')
    source=source.replace('#include "firmware/typed200_trace/trace.h"',
        '#include "firmware/typed200_trace/trace.h"\nstatic FILE *poll_log;\nstatic void observed_poll(struct ty_service *);\n#define ty_service_poll observed_poll')
    anchor='char path[4096];unsigned char buf[384];'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+'''
    #ifdef TRACE_BUILD
    assert(ty_trace.committed && ty_trace.shared_present);
    assert(!memcmp((const void *)ty_trace.shared,(const void *)&shared,384));
    assert(snprintf(path,sizeof(path),"%s/%s.trace.bin",dir,name)>0);
    FILE *tf=fopen(path,"wb");assert(tf);
    assert(fwrite((const void *)&ty_trace,1,sizeof(ty_trace),tf)==sizeof(ty_trace));assert(fclose(tf)==0);
    #endif
''')
    source=source.replace('assert(argc==2);', '''assert(argc==2);
    char poll_path[4096];assert(snprintf(poll_path,sizeof(poll_path),"%s/poll.bin",argv[1])>0);
    poll_log=fopen(poll_path,"wb");assert(poll_log);''')
    source=source.replace('    return 0;\n}', '    assert(fclose(poll_log)==0);return 0;\n}')
    source+='''
#undef ty_service_poll
static void observed_poll(struct ty_service *c) {
    ty_service_poll(c);
    const uint64_t fields[]={c->phase,c->next_request,c->sequence,c->last_sequence,
        c->tokens,c->first,c->count,c->identity.session,c->identity.request,
        c->bridge.state,c->bridge.last_request,c->bridge.identity.session,c->bridge.identity.request,
        c->bridge.proposed_label,c->bridge.proposed_outcome,c->proposal.identity.session,
        c->proposal.identity.request,c->proposal.label,c->proposal.reserved_score,c->proposal.outcome};
    assert(fwrite(fields,1,sizeof(fields),poll_log)==sizeof(fields));
    assert(fwrite((const void *)mmio,1,sizeof(mmio),poll_log)==sizeof(mmio));
    assert(fwrite((const void *)ids,1,sizeof(ids),poll_log)==sizeof(ids));
    assert(fwrite((const void *)&shared,1,sizeof(shared),poll_log)==sizeof(shared));
    assert(fwrite((const void *)permit,1,sizeof(permit),poll_log)==sizeof(permit));
    assert(fwrite(c->identity.contract,1,32,poll_log)==32);
    assert(fwrite(c->proposal.identity.contract,1,32,poll_log)==32);
}
'''
    harness=out/'capture-trace.c';harness.write_text(source)
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--']
    flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-fno-fast-math','-ffp-contract=off',
           '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I.']
    control=out/'control';control.mkdir()
    run([*prefix,'gcc',*flags,'firmware/typed_intent/typed_intent.c','firmware/typed200_v2/typed200.c',
         'firmware/typed200_r5/service.c',rel+'/capture-trace.c','-o',rel+'/capture-control'],'control-compile.log')
    run([*prefix,rel+'/capture-control',rel+'/control'],'control-run.log')
    run([*prefix,'gcc',*flags,'-DTRACE_BUILD','firmware/typed_intent/typed_intent.c','firmware/typed200_v2/typed200.c',
         'firmware/typed200_trace/service.c','firmware/typed200_trace/trace.c',rel+'/capture-trace.c',
         '-o',rel+'/capture-trace'],'compile.log')
    run([*prefix,rel+'/capture-trace',rel],'host-run.log')
    assert (out/'poll.bin').read_bytes()==(control/'poll.bin').read_bytes(),'Per-poll state/proposal/MMIO/IDs/mailbox changed'
    poll_bytes=(out/'poll.bin').stat().st_size
    poll_record_bytes=20*8+256+256+384+4+64
    assert poll_bytes and poll_bytes%poll_record_bytes==0
    run([*prefix,'gcc',*flags,'firmware/typed200_trace/trace.c','firmware/typed200_trace/test_trace.c',
         '-o',rel+'/trace-unit'],'trace-unit-compile.log')
    run([*prefix,rel+'/trace-unit'],'trace-unit.log')
    run([sys.executable,'-m','pytest','tests/test_typed200_trace.py','tests/test_typed200_capture.py',
         '-q','--junitxml='+str(out/'pytest.xml')],'pytest.log')
    baseline=ROOT/'build/v2/typed200-qualification-host-v3'
    results={}
    for case in ('accepted','deadline','fault','cpu-invalid','cpu-fault'):
        for suffix in ('shared.bin','pl.bin'):
            assert (out/f'{case}.{suffix}').read_bytes()==(baseline/f'{case}.{suffix}').read_bytes(),(case,suffix)
            assert (out/f'{case}.{suffix}').read_bytes()==(control/f'{case}.{suffix}').read_bytes(),(case,suffix,'new control')
        fields=json.loads((baseline/f'{case}.expected.json').read_text());fields['token_ids']=tuple(fields['token_ids'])
        results[case]=assess_trace((out/f'{case}.trace.bin').read_bytes(),ExpectedCapture(**fields))
        (out/f'{case}.report.json').write_text(json.dumps(results[case],indent=2)+'\n')
    # Original startup/platform/linker remain unchanged. New service+trace only.
    tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
    cflags=['--target=arm-none-eabi','-mcpu=cortex-r5','-mfpu=vfpv3-d16','-mfloat-abi=hard','-O2',
            '-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-fast-math','-ffp-contract=off',
            '-ffunction-sections','-fdata-sections','-fstack-usage']
    units=['firmware/typed_intent/typed_intent.c','firmware/typed200_v2/typed200.c',
           'firmware/typed200_trace/service.c','firmware/typed200_trace/trace.c',
           *['firmware/typed200_r5/'+n for n in ('sha256.c','platform.c','runtime.c','start.S')]]
    objects=[]
    for i,unit in enumerate(units):
        obj=out/f'unit-{i}.o';objects.append(str(obj))
        run([str(tools/'clang.exe'),*cflags,'-c',unit,'-o',str(obj)],f'arm-compile-{i}.log',env)
    elf=out/'typed200-trace.elf'
    run([str(tools/'ld.lld.exe'),'-T','firmware/typed200_r5/tcm.ld','--gc-sections','--no-undefined',
         '-Map='+str(out/'trace.map'),*objects,'-o',str(elf)],'link.log',env)
    run([str(tools/'llvm-readelf.exe'),'-h','-l','-S','-s',str(elf)],'elf.txt',env)
    run([str(tools/'llvm-objdump.exe'),'-d',str(elf)],'disassembly.txt',env)
    elf_audit=audit(out)
    for p,h in preserved.items():assert sha(ROOT/p)==h,p
    sources=[*[(ROOT/u) for u in units],*[p for p in (ROOT/'firmware/typed200_trace').iterdir() if p.is_file()],
             Path(__file__),ROOT/'scripts/v2/create_typed200_trace.py',ROOT/'src/sysone/v2/typed200_trace.py',
             ROOT/'scripts/v2/audit_typed200_trace.py',ROOT/'tests/test_typed200_trace.py']
    (out/'receipt.json').write_text(json.dumps({'passed':True,'target_executed':False,'wcet_certified':False,
        'baseline_capture_bytes_unchanged':True,'paired_poll_records':poll_bytes//poll_record_bytes,
        'paired_poll_bytes':poll_bytes,'paired_poll_record_bytes':poll_record_bytes,
        'per_poll_state_proposal_mmio_ids_mailbox_match':True,'results':results,'elf_audit':elf_audit,'commands':commands,
        'prior_seal_sha256':sha(seal),'preserved_sha256':preserved,
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'artifact_sha256':{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()},
        'limits':['No target execution; injected-clock capability defaults off',
                  'Additional MMIO reads/instructions perturb timing and can delay CPU progress',
                  'Identical mock outputs do not prove target behavioral/timing equivalence']},indent=2)+'\n')
    print('PASS separate pre-ACK trace, same five fixture outputs, sanitizer tests and R5 ELF link; no target execution')
if __name__=='__main__':main()
