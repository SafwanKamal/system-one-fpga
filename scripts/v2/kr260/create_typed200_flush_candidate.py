"""Isolate the result FIFO synchronous-reset/flush experiment; preserve its parent."""
from pathlib import Path
import argparse,hashlib,json,shutil
from create_typed200_candidate import ROOT,OUT as PARENT,verify as parent_verify
OUT=ROOT/'rtl/v2/candidates/typed200_flush'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory():return {p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.suffix in ('.sv','.v')}
def create():
    parent=parent_verify();assert parent['sealed']
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(PARENT,OUT)
    fifo=(PARENT/'common/sync_fifo.sv').read_text()
    fifo=fifo.replace('module sync_fifo #(','module stream_fifo_sync_clear #(',1)
    fifo=fifo.replace('    input logic reset,','    input logic reset,\n    input logic clear,',1)
    fifo=fifo.replace('write_enable && !full','write_enable && !full && !reset && !clear')
    fifo=fifo.replace('read_enable && !empty','read_enable && !empty && !reset && !clear')
    fifo=fifo.replace('always_ff @(posedge clk or posedge reset)','always_ff @(posedge clk)')
    fifo=fifo.replace('        if (reset) begin','        if (reset || clear) begin',1)
    fifo='// Candidate: reset and per-descriptor clear are sampled synchronously.\n// Reset must span a clock edge; no start/clear signal drives an async pin.\n'+fifo
    (OUT/'common/stream_fifo_sync_clear.sv').write_text(fifo)
    p=OUT/'encoder/result_streamer.sv';s=p.read_text()
    s=s.replace('assign valid = !empty;','assign valid = !empty && !start && !reset;')
    s=s.replace('sync_fifo #(','stream_fifo_sync_clear #(',1)
    s=s.replace('.clk(clk), .reset(reset || start),','.clk(clk), .reset(reset), .clear(start),',1)
    p.write_text(s)
    m={'candidate':'typed200_flush','sealed':False,'parent_manifest_sha256':sha(PARENT/'candidate.json'),
       'parent_source_sha256':parent['candidate_sha256'],'candidate_sha256':inventory(),
       'target_mhz':200,'hardware_qualified':False,'abi':parent['abi'],'contract_sha256':parent['contract_sha256'],
       'changes':['New synchronous-reset/clear result FIFO only','Mask output valid during reset/start'],
       'reset_assumption':'Reset spans at least one clock edge and has synchronous release',
       'numerical_contract_changed':False,'deadline_or_epoch_logic_changed':False}
    (OUT/'candidate.json').write_text(json.dumps(m,indent=2)+'\n')
def verify(seal=False):
    parent_verify();m=json.loads((OUT/'candidate.json').read_text())
    assert m['parent_manifest_sha256']==sha(PARENT/'candidate.json')
    assert m['parent_source_sha256']==json.loads((PARENT/'candidate.json').read_text())['candidate_sha256']
    actual=inventory()
    allowed={'encoder/result_streamer.sv','common/stream_fifo_sync_clear.sv'}
    changed={p for p in actual if actual[p]!=m['parent_source_sha256'].get(p)}
    assert changed==allowed,changed
    assert set(actual)==set(m['parent_source_sha256'])|{'common/stream_fifo_sync_clear.sv'}
    if seal:
        assert not m['sealed'];m['candidate_sha256']=actual;m['sealed']=True
        (OUT/'candidate.json').write_text(json.dumps(m,indent=2)+'\n')
    assert actual==m['candidate_sha256']
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');p.add_argument('--seal',action='store_true');a=p.parse_args()
    verify(a.seal) if a.verify or a.seal else create()
    print('PASS isolated synchronous result-FIFO candidate; sealed parent unchanged')
