"""Live FPGA INT8 tool command, automatic MiniLM restoration, onboard Qwen response.

Not run by preparation. Requires matching baseline image and rollback module.
Does not program PL, start JTAG, reboot Linux or change dashboard/entrypoints.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--bundle',type=Path,required=True)
    ap.add_argument('--baseline-image',type=Path,required=True);ap.add_argument('--rollback-module',type=Path,required=True)
    ap.add_argument('--request',type=Path)
    ap.add_argument('--query')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--qwen-url',default='http://127.0.0.1:8016')
    ap.add_argument('--no-qwen',action='store_true')
    args=ap.parse_args()
    if os.geteuid()!=0:raise RuntimeError('root required inside explicitly authorized board window')
    sys.path.insert(0,str(args.repo/'src'))
    from sysone.v2.kr260_link import Kr260Link
    from sysone.v2.kr260_runtime import discover_memory
    from sysone.v2.ddr_image import parse_header
    from tokenizers import Tokenizer
    control=Path('/sys/class/misc/sysone_r5_smoke')
    bundle=args.bundle.resolve();candidate=json.loads((bundle/'candidate.json').read_text())
    preparation=json.loads((bundle/'runtime-preparation.json').read_text())
    if digest(bundle/'candidate.img')!=candidate['image_sha256']:raise RuntimeError('changed image')
    for name,sha in preparation['module_sha256'].items():
        if digest(bundle/'linux-module-candidate'/name)!=sha:raise RuntimeError('changed module source')
    source=args.repo/'scripts/v2/general_encoder_mvp_client_v1.py'
    if digest(source)!=next(v for k,v in preparation["source_sha256"].items() if k.replace(chr(92),"/")=="scripts/v2/general_encoder_mvp_client_v1.py"):
        raise RuntimeError('changed ingress source')
    # Build against this running kernel before disturbing the working system.
    subprocess.run(['make','-C','/lib/modules/'+os.uname().release+'/build','M='+str(bundle/'linux-module-candidate'),'modules'],check=True)
    baseline=args.baseline_image.read_bytes();image=(bundle/'candidate.img').read_bytes()
    rollback=args.rollback_module.resolve()
    spec=importlib.util.spec_from_file_location('mvp_client',source);client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    spec2=importlib.util.spec_from_file_location('helpers',bundle/'runtime/helpers.py');helpers=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(helpers)
    tok=Tokenizer.from_file(str(bundle/'runtime/tokenizer.json'));tok.no_truncation();tok.no_padding()
    import mvp_tool_runtime_v1 as runtime
    args.out.parent.mkdir(parents=True,exist_ok=True)
    request_path=args.request or args.out.with_name('request-'+str(__import__('time').monotonic_ns())+'.json')
    if args.query:
        request_path.write_text(json.dumps(dict(query=args.query,tools=runtime.registered_tools())))
    request=json.loads(request_path.read_text())
    if request['tools']!=runtime.registered_tools():raise ValueError('Use the registered live tool schema')
    started=__import__('time').monotonic()
    def command(s):(control/'command').write_text(s+'\n')
    def idle():
        status=(control/'status').read_text()
        if any(k+'=1' in status for k in ['pinned','mapped','may_run','quarantine']):raise RuntimeError('R5 not safely idle; stop and inspect')
    with Path('/run/lock/sysone-inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        status=(control/'status').read_text();identity=next(x.split('=',1)[1] for x in status.split() if x.startswith('image_sha256='))
        if identity.encode() not in rollback.read_bytes():raise RuntimeError('rollback module does not match active firmware identity')
        command('stop');idle()
        link=Kr260Link(memory=discover_memory())
        try:
            if link._r(0)&1:raise RuntimeError('PL busy; no switch')
            link.verify_loaded_image(0x60000000,baseline)
            layout=SimpleNamespace(ids=int(candidate['layout']['ids'],16),result=int(candidate['layout']['hidden'],16),max_tokens=128,hidden=768)
            link.validate_image(parse_header(image),len(image),layout)
            subprocess.run(['rmmod','sysone_r5_smoke'],check=True)
            loaded=False;switched=False
            try:
                link.write(0x60000000,image);switched=True;link.verify_loaded_image(0x60000000,image)
                subprocess.run(['insmod',str(bundle/'linux-module-candidate/sysone_r5_smoke.ko')],check=True);loaded=True
                backend=client.EncoderBackend(bundle,False)
                calls=client.infer(request['query'],request['tools'],tok,backend,helpers)
                tool_results=runtime.execute_calls(calls)
                result=dict(query=request['query'],calls=calls,tool_results=tool_results,tools_executed=True,
                    parser_backend='R5_controlled_FPGA_INT8_and_R5_integer_heads',host_fp32_correction=False,
                    encoder_passes=backend.passes,request_sha256=digest(request_path),
                    image_sha256=candidate['image_sha256'],r5_elf_sha256=candidate['r5_elf_sha256'])
                (bundle/'physical-smoke.json').write_text(json.dumps(dict(board_executed=True,r5_controls_pl=True,
                    r5_computes_logits=True,calls=calls,encoder_passes=backend.passes,tools_executed=True,
                    request_sha256=digest(request_path),image_sha256=candidate['image_sha256'],
                    r5_elf_sha256=candidate['r5_elf_sha256'],evidence_mode='live_board_smoke',
                    semantic_accuracy_qualified=False,terminal_by_D_qualified=False),indent=2)+'\n')
            finally:
                # Never overwrite memory or unload a possibly active controller.
                if loaded:command('stop');idle()
                if link._r(0)&1:raise RuntimeError('PL still busy; leave candidate for inspection, no forced restore')
                if loaded:subprocess.run(['rmmod','sysone_r5_smoke'],check=True)
                if switched:link.write(0x60000000,baseline);link.verify_loaded_image(0x60000000,baseline)
                subprocess.run(['insmod',str(rollback)],check=True)
                if 'image_sha256='+identity not in (control/'status').read_text():raise RuntimeError('restored firmware identity mismatch')
                (bundle/'rollback-result.json').write_text(json.dumps(dict(model_restored=True,r5_module_restored=True,linux_running=True))+'\n')
        finally:link.close()
    result['restoration']=json.loads((bundle/'rollback-result.json').read_text())
    result['linux_boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    if not args.no_qwen:
        try:result['generation']=runtime.generate_response(request['query'],tool_results,args.qwen_url)
        except Exception as exc:
            result['complete']=False;result['generation_error']=type(exc).__name__+': '+str(exc)
            args.out.write_text(json.dumps(result,indent=2)+'\n')
            raise
    result['elapsed_ms']=(__import__('time').monotonic()-started)*1000
    result['complete']=args.no_qwen or result['generation']['grounded_in_tool_result']
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['complete']:raise RuntimeError('Qwen response did not contain the actual tool result; inspect saved output')


if __name__=='__main__':main()
