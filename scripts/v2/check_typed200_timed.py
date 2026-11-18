"""Derive a separately staged timed experiment from the sealed trace runner."""
from pathlib import Path
import argparse,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args()
    import re
    if not re.fullmatch(r'typed200-timed-host-v[0-9]+',a.name):raise ValueError('New unique timed name required')
    runner=ROOT/'build/v2'/f'{a.name}-runner.py';assert not runner.exists()
    s=(ROOT/'scripts/v2/check_typed200_trace.py').read_text()
    def replace(old,new):
        nonlocal s
        assert s.count(old)==1,old
        s=s.replace(old,new)
    replace("ROOT=Path(__file__).resolve().parents[2]",'ROOT=Path('+repr(str(ROOT))+')\nsys.path.insert(0,str(ROOT/"scripts/v2"))')
    replace('from sysone.v2.typed200_trace import assess_trace','from sysone.v2.typed200_timed import assess_timed_trace')
    replace('from audit_typed200_trace import audit','from audit_typed200_timed import audit')
    replace("r'typed200-trace-host-v[0-9]+'","r'typed200-timed-host-v[0-9]+'")
    replace('2026-10-15-typed200-capture-validation.json','2026-10-15-typed200-owner-trace-validation.json')
    replace("('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256')",
            "('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256','historical_evidence_sha256')")
    # A copied host-only service test configures the mock PMU before every init.
    anchor="    # Reuse the frozen host harness, adding export assertions only in this copy."
    replace(anchor,'''    test=(ROOT/'firmware/typed200_r5/test_service.c').read_text()
    test=test.replace('#include "service.h"','#include "firmware/typed200_r5/service.h"')
    test=test.replace('static void init(void) {', '\\n'.join([
        'static void init(void) {','#ifdef TRACE_BUILD',
        'ty_pmu_config.magic=TY_PMU_CONFIG_MAGIC;ty_pmu_config.version=1;',
        'ty_pmu_config.session=0x12345678;ty_pmu_config.cpu_hz=500000000;ty_pmu_config.exclusive_pmu_attested=1;',
        'ty_mock_pmcr=0x41151801;ty_mock_enable=0x80000000;ty_mock_irq=0;ty_mock_overflow=0;ty_mock_tick=100;ty_mock_step=100;',
        'assert(ty_pmu_bind(0x12345678));','#endif']))
    (out/'test-service-timed.c').write_text(test)
'''+anchor)
    # This anchor is a line in the runner; replace with runtime source edits.
    anchor="    harness=out/'capture-trace.c';harness.write_text(source)"
    replace(anchor,'''    source=source.replace('#include "firmware/typed200_trace/trace.h"',
        '#include "firmware/typed200_trace/trace.h"\\n#include "firmware/typed200_timed/pmu.h"')
    source=source.replace('#include "firmware/typed200_r5/test_service.c"',
        '#include "'+rel+'/test-service-timed.c"')
    source=source.replace('    #endif\\n', '\\n'.join([
        '    assert(snprintf(path,sizeof(path),"%s/%s.pmu.bin",dir,name)>0);',
        '    tf=fopen(path,"wb");assert(tf);',
        '    assert(fwrite((const void *)&ty_pmu_evidence,1,sizeof(ty_pmu_evidence),tf)==sizeof(ty_pmu_evidence));assert(fclose(tf)==0);',
        '    #endif','']))
'''+anchor)
    replace("*flags,'-DTRACE_BUILD'","*flags,'-DTRACE_BUILD','-DTY_PMU_HOST_TEST'")
    replace("'firmware/typed200_trace/service.c','firmware/typed200_trace/trace.c',rel+'/capture-trace.c'",
            "'firmware/typed200_trace/service.c','firmware/typed200_trace/trace.c','firmware/typed200_timed/pmu.c',rel+'/capture-trace.c'")
    anchor="    baseline=ROOT/'build/v2/typed200-qualification-host-v3'"
    replace(anchor,'''    run([*prefix,'gcc',*flags,'-DTY_PMU_HOST_TEST','firmware/typed200_trace/trace.c',
        'firmware/typed200_timed/pmu.c','firmware/typed200_timed/test_pmu.c','-o',rel+'/pmu-unit'],'pmu-unit-compile.log')
    run([*prefix,rel+'/pmu-unit'],'pmu-unit.log')
'''+anchor)
    replace("'tests/test_typed200_trace.py','tests/test_typed200_capture.py'",
            "'tests/test_typed200_timed.py','tests/test_typed200_trace.py','tests/test_typed200_capture.py'")
    replace("results[case]=assess_trace((out/f'{case}.trace.bin').read_bytes(),ExpectedCapture(**fields))",
            "results[case]=assess_timed_trace((out/f'{case}.trace.bin').read_bytes(),(out/f'{case}.pmu.bin').read_bytes(),ExpectedCapture(**fields))")
    replace("*['firmware/typed200_r5/'+n for n in ('sha256.c','platform.c','runtime.c','start.S')]",
            "'firmware/typed200_timed/pmu.c','firmware/typed200_timed/platform.c',*['firmware/typed200_r5/'+n for n in ('sha256.c','runtime.c','start.S')]")
    replace("'-T','firmware/typed200_r5/tcm.ld'","'-T','firmware/typed200_timed/tcm.ld'")
    anchor="    for p,h in preserved.items():assert sha(ROOT/p)==h,p"
    replace(anchor,'''    dis=(out/'disassembly.txt').read_text()
    assert 'c9, c13, #0' in dis or 'c9, c13, 0' in dis,'Missing PMCCNTR read'
'''+anchor)
    replace("ROOT/'tests/test_typed200_trace.py']", "ROOT/'tests/test_typed200_trace.py',ROOT/'scripts/v2/check_typed200_timed.py',\n             ROOT/'scripts/v2/audit_typed200_timed.py',ROOT/'src/sysone/v2/typed200_timed.py',\n             ROOT/'tests/test_typed200_timed.py',*[p for p in (ROOT/'firmware/typed200_timed').iterdir() if p.is_file()]]")
    replace('No target execution; injected-clock capability defaults off',
            'No target execution; timed platform requires loader-configured full-rate owned PMU and fresh matching config')
    replace('PASS separate pre-ACK trace, same five fixture outputs, sanitizer tests and R5 ELF link; no target execution',
            'PASS separate timed PMU candidate, mock fault tests and exact control poll comparison; ARM ELF audited, no target execution')
    runner.write_text(s)
    raise SystemExit(subprocess.run([sys.executable,str(runner),'--name',a.name],cwd=ROOT).returncode)
if __name__=='__main__':main()
