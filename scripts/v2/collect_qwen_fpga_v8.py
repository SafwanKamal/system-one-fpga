"""Seal one successful sub-ten-second FPGA command and its build evidence."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v8'


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1<<20),b''):digest.update(chunk)
    return digest.hexdigest()


def main():
    assert not (BUILD/'seal.json').exists(),'Preserve the completed release'
    results=BUILD/'board/results'
    for job in ['05-refresh-qualified-baseline','06-upload-qualified-wide-int8',
                '07-extract-qualified-wide-int8','08-reset-manager-state',
                '08-retry-qualified-deployment',
                '09-causal-hardware-smoke','10-one-cold-real-command',
                '13-upload-pipelined-startup','14-verify-startup-package',
                '15-cold-command-pipelined-startup','16-promote-under-ten-seconds',
                '17-collect-final-evidence',
                '99-close-session']:
        assert json.loads((results/job/'receipt.json').read_text())['exit']==0,job
    assert json.loads((results/'08-deploy-wide-int8/receipt.json').read_text())['exit']==1
    assert json.loads((results/'11-promote-faster-deployment/receipt.json').read_text())['exit']==1
    data=json.loads((results/'17-collect-final-evidence/stdout').read_text())
    proof=data['deployment-proof.json'];r=data['real-command-result.json']
    baseline_path=ROOT/'build/v2/qwen-fpga-decoder-v7/deployment-proof.json'
    previous=json.loads(baseline_path.read_text())
    assert proof['baseline_deployment_sha256']==hashlib.sha256(baseline_path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert proof['complete'] and proof['target_10_seconds_met'] and r['complete']
    assert proof['real_command']==r and r['elapsed_seconds']<10
    assert proof['baseline_profile']['command']==previous['real_command']
    assert r['prompt_ids']==previous['real_command']['prompt_ids']
    assert r['call']==previous['real_command']['call'] and r['tools_executed']
    assert r['tool_result']['text']==r['linux_boot_id']==data['linux_boot_id_now']
    assert r['model_sha256']==previous['real_command']['model_sha256']
    assert r['resident_weights_verified'] and r['prefix_tokens_reused']==0
    assert not r['ARM_model_inference'] and not r['host_model_inference']
    assert data['residency_reused']
    first=data['first_command']
    assert first['complete'] and first['tools_executed'] and first['call']==r['call']
    (BUILD/'first-command-result.json').write_text(json.dumps(first,indent=2)+'\n')
    for name in ['deployment-proof.json','real-command-result.json',
                 'hardware-block-smoke.json','deployment-state.json']:
        (BUILD/name).write_text(json.dumps(data[name],indent=2)+'\n')
    for name,digest in proof['package_files_verified'].items():
        assert sha(BUILD/'deployment'/name)==digest,name
    for name,digest in json.loads((BUILD/'hardware-source-sha256.json').read_text()).items():
        assert sha(ROOT/name)==digest,name
    old={}
    for version in range(2,8):
        path=ROOT/f'build/v2/qwen-fpga-decoder-v{version}/seal.json'
        seal=json.loads(path.read_text())
        for name,digest in seal['files_sha256'].items():
            assert sha(ROOT/name)==digest,'Prior sealed file changed: '+name
        old[str(version)]=dict(files=len(seal['files_sha256']),seal_sha256=sha(path),unchanged=True)
    full_job=json.loads((results/'15-cold-command-pipelined-startup/receipt.json').read_text())['elapsed_seconds']
    smoke=data['hardware-block-smoke.json'];worst=max(c['max_absolute_error'] for c in smoke['cases'])
    summary=f'''# Sub-ten-second Qwen0.6B FPGA tool command — 2026-10-21

One real cold-prefill command completed in **{r['elapsed_seconds']:.9f}s**
(full SSH job {full_job:.3f}s), versus v7 {previous['real_command']['elapsed_seconds']:.9f}s:
{proof['speedup']:.4f}x and {proof['time_reduction_percent']:.2f}% less time.
This is one focused command, not a benchmark sweep or worst-case timing claim.

The FPGA generated read_linux_file('/proc/sys/kernel/random/boot_id'), and Linux
executed it, returning current boot {r['linux_boot_id']}. The same Linux boot and
639446688-byte pinned Q8_0 model residency were retained. All NN arithmetic is on
the FPGA; no ARM/host NN, argument correction, output replay or vocabulary mask.
Zero prefix reuse. Model loading at boot is separate; cold-call timing includes
tokenizer startup and verification of every resident weight byte, as in v7.

Arithmetic precision changed: matrix inputs use dynamic symmetric INT8 per block
of 32, with ties rounded away from zero and saturation to [-127,127]. Weights
are the unchanged pinned Q8_0 bytes. Dot products accumulate INT32, then use
FP32 scales/partials. Norms, RoPE, attention, KV and residuals remain FP32.
This is not a claim of numerical equivalence to the prior FP32 matrix engine.
Generated IDs equal v7: {proof['generated_ids_match_baseline']}.

Hardware improvements: 256-bit weight stream; 125MHz decoder and 250MHz,
128-bit PS memory interface through a clock/width converter; eight-token
prefill weight reuse; one matrix block per cycle; paired query heads sharing
K/V reads; causal head-buffer reuse across a prompt batch; quantized input
reuse for Q/K/V and gate/up; shared deep URAM token banks.

Host setup uses native tokenizers 0.23.2 NFC/Split/ByteLevel operations and
compiled ranked BPE tables from the pinned official tokenizer. This avoids
constructing a full native BPE model while holding Python's GIL. Eight focused
normalization/Unicode/whitespace/special-token cases matched official IDs;
the exact prior prompt IDs and generated output bytes also matched. The ARM
wheel, official source and compiled tables are hashed. No CPU NN is loaded.
Ordered SHA256 checks every resident byte before FPGA inference and inside
the timer. Four bounded native staging buffers are immediately refilled after
SHA consumption, pipelining upcoming DMA reads with ordered hashing.

Prefill {r['prefill_seconds']:.6f}s; subsequent decode {r['decode_seconds']:.6f}s;
startup wall {r['startup_wall_seconds']:.6f}s. SHA {r['model_verify_ms']/1000:.6f}s
and vocabulary {r['vocabulary_setup_seconds']:.6f}s are measured within startup;
the wall measurement includes setup overhead and any task overlap.
Prompt/output tokens: {len(r['prompt_ids'])}/{len(r['generated_ids'])}; weight
passes {r['layer_weight_passes']}; full-vocabulary rows {r['vocabulary_rows_projected']}.

The first v8 command was correct but took {first['elapsed_seconds']:.6f}s,
including {first['startup_wall_seconds']:.6f}s startup. Promotion was refused.
After the compiled tokenizer and pipelined SHA changes, the second cold command
above passed. The FPGA image and causal fixture were unchanged. Both commands
and the failed threshold check are retained. No benchmark sweep was run.

Independent NumPy integer-dot and ordered FP32 reference: eight-token causal
layer, full8 and1+7, final norm, top32 argmax4 and scatter boundary passed Csim.
The board's {len(smoke['cases'])} causal fixture cases passed, worst error
{worst:.9g} against that INT8 reference, not against original FP32 matrix math.
Generic matrix capacity6144 at columns2048/6144/1056 also passed Csim.

Geometry derives from the model profile, and tensor alignment and clock guards
run before NN commands. Larger models still require their own weights, memory
allocation, quantization/quality validation and routed fit. No larger model was
deployed. The current DMA table remains limited to 64x16MiB.

Active app: {proof['fpga_app']}; launcher /usr/local/bin/sysone-qwen-fpga.
Previous launcher, firmware and release seals retained. Linux stayed running.
Model/FPGA residency lasts for this boot; package and launcher persist on disk.

The first load attempt stopped before NN inference because dfx-mgr had restarted
while an old configfs overlay remained applied. Its failed receipt is retained.
After checking idle state and absence of MMIO clients, only that verified orphan
overlay was removed and the manager restarted. Baseline reload and candidate
deployment then passed. Linux and the resident DMA buffers were retained.

Evidence: deployment-proof.json, real-command-result.json, hardware-block-smoke.json,
hardware-source-sha256.json, ip-rtl-consistency.json, tokenizer-correctness.json,
tokenizer-wheel-source.json, traffic-plan.json, routed reports under vivado/,
and board queue receipts. All earlier v2-v7 seals were verified unchanged.
'''
    (BUILD/'README.md').write_text(summary,encoding='utf-8')
    doc=ROOT/'docs/research/2026-10-21-under10-qwen06b-fpga-tool-command.md'
    doc.write_text(summary,encoding='utf-8')
    paths={p for p in BUILD.iterdir() if p.is_file()}
    for folder in ['board','block-fixture','deployment','deployment-first']:
        paths.update(p for p in (BUILD/folder).rglob('*') if p.is_file())
    for name in ['qwen_decoder.xsa','routed-timing.rpt','routed-utilization.rpt',
                 'qwen_decoder_kr260.runs/impl_1/system_wrapper.bit',
                 'qwen_decoder_kr260.runs/impl_1/system_wrapper_bus_skew_postroute_physopted.rpt',
                 'qwen_decoder_kr260.runs/impl_1/system_wrapper_timing_summary_postroute_physopted.rpt',
                 'qwen_decoder_kr260.runs/impl_1/system_wrapper_methodology_drc_routed.rpt']:
        paths.add(BUILD/'vivado'/name)
    for name in ['solution/syn/report/qwen_decoder_csynth.xml',
                 'solution/syn/report/qwen_decoder_csynth.rpt',
                 'solution/impl/ip/component.xml',
                 'solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h',
                 'solution/.autopilot/db/qwen_decoder.pp.0.cpp']:
        paths.add(BUILD/'hls-release'/name)
    paths.update(p for p in (ROOT/'hls/qwen_decoder_v8').iterdir() if p.is_file())
    paths.update(ROOT/'scripts/v2'/name for name in [
        'prepare_qwen_fpga_v3.py','complete_qwen_fpga_v8.py','collect_qwen_fpga_v8.py',
        'compile_qwen_tokenizer_v1.py',
        'package_qwen_fpga_v7.py','deploy_qwen_fpga_v7.py','smoke_qwen_fpga_v7.py',
        'finish_qwen_fpga_v7.py','run_qwen_fpga_command_v7.py',
        'qwen_fpga_board_window_ssh_v7.py','check_qwen_hls_export_v2.py'])
    paths.add(ROOT/'src/sysone/v2/qwen_fpga_runtime_v7.py');paths.add(doc)
    paths.add(ROOT/'src/sysone/v2/qwen_tokenizer_v1.py')
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}
    seal=dict(status='UNDER_10_SECONDS_DEPLOYED',date='2026-10-21',
              linux_boot_id=r['linux_boot_id'],elapsed_seconds=r['elapsed_seconds'],
              full_ssh_job_seconds=full_job,target_10_seconds_met=True,
              speedup=proof['speedup'],old_seals=old,files_sha256=hashes)
    (BUILD/'seal.json').write_text(json.dumps(seal,indent=2)+'\n')
    print(json.dumps(dict(sealed_files=len(hashes),elapsed_seconds=r['elapsed_seconds'],
                         full_ssh_job_seconds=full_job,old_seals=old)))


if __name__=='__main__':main()
