"""Boot file gates and backward-compatible launcher behavior without hardware."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location('rc1_'+name,ROOT/'firmware/rc1_default'/(name+'.py'))
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.skipif(sys.platform=='win32',reason='Boot initializer imports Linux fcntl')
def test_boot_gate_rejects_changed_or_escaping_files(tmp_path):
    boot=module('initialize')
    (tmp_path/'asset').write_bytes(b'approved')
    digest=boot.sha(tmp_path/'asset')
    boot.verify_files(tmp_path,{'asset':digest})
    (tmp_path/'asset').write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='Pinned file'):
        boot.verify_files(tmp_path,{'asset':digest})
    with pytest.raises(RuntimeError,match='Pinned file'):
        boot.verify_files(tmp_path,{'../outside':digest})


def test_launcher_flattens_result_preserves_output_and_requests_cold_reset(tmp_path,monkeypatch,capsys):
    launcher=module('launcher')
    calls=[]
    def exchange(path,request):
        calls.append(request)
        return dict(ok=True,result=dict(complete=True,generated_ids=[1,2],prefix_tokens_reused=0),client_seconds=1.5)
    monkeypatch.setitem(sys.modules,'qwen_arm_service_candidate',SimpleNamespace(exchange=exchange))
    output=tmp_path/'result.json'
    monkeypatch.setattr(sys,'argv',['sysone-qwen-fpga','--query','Read /proc/uptime','--out',str(output),
                                  '--max-tokens','32','--no-prefix-cache'])
    launcher.main()
    result=json.loads(output.read_text())
    assert result['complete'] and result['generated_ids']==[1,2] and 'result' not in result
    assert calls==[dict(op='generate',query='Read /proc/uptime',max_tokens=32,
                        conversation_id='default',reset_cache=True)]


def test_launcher_fault_has_nonzero_exit_and_no_fallback(tmp_path,monkeypatch):
    launcher=module('launcher')
    monkeypatch.setitem(sys.modules,'qwen_arm_service_candidate',SimpleNamespace(
        exchange=lambda *a:dict(ok=False,state='FAULTED',error='identity changed')))
    output=tmp_path/'failure.json'
    monkeypatch.setattr(sys,'argv',['sysone-qwen-fpga','--query','x','--out',str(output)])
    with pytest.raises(SystemExit) as exc:launcher.main()
    assert exc.value.code==1
    result=json.loads(output.read_text())
    assert not result['complete'] and result['state']=='FAULTED'


def test_health_does_not_write_generation_output(tmp_path,monkeypatch,capsys):
    launcher=module('launcher')
    monkeypatch.setitem(sys.modules,'qwen_arm_service_candidate',SimpleNamespace(
        exchange=lambda path,request:dict(ok=True,state='READY')))
    output=tmp_path/'unused.json'
    monkeypatch.setattr(sys,'argv',['sysone-qwen-fpga','--health','--out',str(output)])
    launcher.main()
    assert not output.exists()
    assert json.loads(capsys.readouterr().out)['state']=='READY'
