"""Bind matched native synthesis/analysis evidence; no physical qualification."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[3]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def utilization(p):
    text=p.read_text()
    result={}
    for label,key in [('CLB LUTs*','lut'),('CLB Registers','ff'),('DSPs','dsp'),('Block RAM Tile','bram_tiles'),('URAM','uram')]:
        m=re.search(r'\|\s*'+re.escape(label)+r'\s*\|\s*(\d+)\s*\|',text)
        assert m,label
        result[key]=int(m[1])
    return result


def main():
    b=ROOT/'build/v2/typed200-synthesis-clock-v3'
    dest=b/'clock-experiment-review.json'
    assert not dest.exists()
    inputs=json.loads((b/'input-proof.json').read_text())
    for n,row in inputs['inputs'].items():
        assert sha(b/n)==sha(ROOT/row['source'])==row['sha256'],n
    reuse=json.loads((b/'control-reuse.json').read_text())
    assert reuse['matched_inputs']
    assert sha(b/'control/encoder.dcp')==reuse['checkpoint_sha256']==sha(ROOT/'build/v2'/reuse['source']/'control/encoder.dcp')
    assert (b/'encoder-ooc.xdc').read_text()=='create_clock -name encoder_ooc_200 -period 5.000 [get_ports clk]\n'
    checksums={}
    results={}
    for mode in ['control','clocked']:
        assert json.loads((b/mode/'status.json').read_text())['exit_code']==0
        text=(b/mode/'console.log').read_text()
        assert '0 Critical Warnings and 0 Errors encountered.' in text
        checksums[mode]=re.search(r'Synth Design complete \| Checksum: ([0-9a-f]+)',text)[1]
        timing=json.loads((b/f'{mode}-analysis/timing.json').read_text())
        report=(b/f'{mode}-analysis/timing.rpt').read_text()
        row=re.search(r'WNS\(ns\).*?\n\s*[- ]+\n([^\n]+)',report,re.S)[1].split()
        assert float(row[0])==timing['setup_ns'] and float(row[4])==timing['hold_ns']
        assert timing['period_ns']==5.0 and not timing['routed']
        results[mode]={'timing':timing,'resources':utilization(b/mode/'utilization.rpt')}
    old=(ROOT/'build/v2/typed200-flush-physical-v1/sysone_v2_kr260.runs/system_encoder_0_synth_1/runme.log').read_text()
    assert re.search(r'Synth Design complete \| Checksum: ([0-9a-f]+)',old)[1]==checksums['control']
    text=(b/'clocked/console.log').read_text()
    assert text.index('Parsing XDC File [S:/build/v2/typed200-synthesis-clock-v3/encoder-ooc.xdc]')<text.index('Start Timing Optimization')
    assert json.loads((b/'clocked/status.json').read_text())['clock_applied_during_synthesis']
    assert (b/'clocked/clock-count.txt').read_text().splitlines()==['Stored OOC clocks: 1','encoder_ooc_200 period 5.000']
    assert (b/'control/clock-count.txt').read_text().strip()=='Stored OOC clocks: 0'
    assert 'Exiting Vivado' in (b/'analysis-console.log').read_text()
    evidence=[b/'input-proof.json',b/'control-reuse.json',b/'encoder-ooc.xdc',b/'analysis-console.log',
              *[p for mode in ['control','clocked','control-analysis','clocked-analysis']
                for p in (b/mode).iterdir() if p.is_file() and p.suffix in ('.rpt','.json','.txt','.dcp','.tcl','.log')]]
    result={'ooc_experiment_validated':True,'same_rtl':True,'same_analysis_period_ns':5.0,
        'mapping_checksums':checksums,'control_reproduces_frozen_parent_mapping':True,
        'results':results,'estimated_setup_delta_ns':round(results['clocked']['timing']['setup_ns']-results['control']['timing']['setup_ns'],3),
        'lut_delta':results['clocked']['resources']['lut']-results['control']['resources']['lut'],
        'composed_physical_pending':True,'hardware_qualified':False,'deployment_approved':False,
        'limits':['OOC input/output delays unspecified','HD.CLK_SRC/top clock skew context absent',
                  'estimated interconnect, no placement/routing','no hardware speedup or WCET inference'],
        'evidence_sha256':{p.relative_to(b).as_posix():sha(p) for p in evidence}}
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS matched OOC experiment; estimated setup delta',result['estimated_setup_delta_ns'],'ns; LUT delta',result['lut_delta'])


if __name__=='__main__':
    main()
