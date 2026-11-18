"""Collect the one-command deployment evidence and preserve prior release seals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/'build/v2/qwen-fpga-decoder-v7'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if (BUILD/'seal.json').exists():
        raise RuntimeError('Release already sealed; preserve the existing result')
    results = BUILD/'board/results'
    for name in ['05-refresh-qualified-baseline', '06-upload-qualified-buffered',
                 '07-extract-qualified-buffered', '08-deploy-buffered',
                 '09-causal-hardware-smoke', '10-one-cold-real-command',
                 '11-promote-faster-deployment', '12-collect-deployment-evidence',
                 '99-close-session']:
        receipt = json.loads((results/name/'receipt.json').read_text())
        assert receipt['exit'] == 0, name
    data = json.loads((results/'12-collect-deployment-evidence/stdout').read_text())
    proof = data['deployment-proof.json']
    command = data['real-command-result.json']
    assert proof['complete'] and proof['generated_ids_match_baseline']
    assert proof['real_command'] == command
    assert command['complete'] and command['tools_executed']
    assert not command['ARM_model_inference'] and not command['host_model_inference']
    assert command['prefix_tokens_reused'] == 0
    # The prior local evidence was saved with Windows CRLF; the board's proof
    # uses LF. Compare its exact Linux byte representation, while the release
    # seal below independently verifies the unchanged original Windows bytes.
    prior = ROOT/'build/v2/qwen-fpga-decoder-v6/deployment-proof.json'
    assert proof['baseline_deployment_sha256'] == hashlib.sha256(prior.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    assert proof['baseline_profile']['command'] == json.loads(prior.read_text())['real_command']
    for name in ['deployment-proof.json', 'real-command-result.json',
                 'hardware-block-smoke.json', 'deployment-state.json']:
        (BUILD/name).write_text(json.dumps(data[name], indent=2)+'\n')
    (BUILD/'boot-recovery.json').write_text(json.dumps(data['boot-recovery'], indent=2)+'\n')
    for name, digest in proof['package_files_verified'].items():
        assert sha(BUILD/'deployment'/name) == digest, name
    frozen = json.loads((BUILD/'hardware-source-sha256.json').read_text())
    for name, digest in frozen.items():
        assert sha(ROOT/name) == digest, name
    old = {}
    for version in [2, 3, 4, 5, 6]:
        path = ROOT/f'build/v2/qwen-fpga-decoder-v{version}/seal.json'
        previous = json.loads(path.read_text())
        for name, digest in previous['files_sha256'].items():
            assert sha(ROOT/name) == digest, 'Prior sealed file changed: '+name
        old[str(version)] = dict(files=len(previous['files_sha256']), seal_sha256=sha(path), unchanged=True)
    seconds = command['elapsed_seconds']
    baseline = proof['baseline_profile']['command']['elapsed_seconds']
    smoke = data['hardware-block-smoke.json']
    worst = max(case['max_absolute_error'] for case in smoke['cases'])
    full_job = json.loads((results/'10-one-cold-real-command/receipt.json').read_text())['elapsed_seconds']
    summary = f'''# Buffered Qwen0.6B FPGA decoder deployment — 2026-10-20

One cold-prefill real tool command completed in **{seconds:.9f} seconds**
(SSH job {full_job:.3f}s), versus the historical v6 {baseline:.9f}s:
{proof['speedup']:.4f}x, {proof['time_reduction_percent']:.2f}% less time.
The 10-second target is {'met' if seconds < 10 else 'not yet met'}.

The model generated the same {len(command['generated_ids'])} IDs for the same
{len(command['prompt_ids'])}-ID prompt, with zero prefix reuse. The generated
read_linux_file('/proc/sys/kernel/random/boot_id') command executed on Linux and
returned current boot {command['linux_boot_id']}. All NN arithmetic remains on
the FPGA with Q8_0 weights and FP32 activations. No ARM/host NN or argument
correction. Full vocabulary and identical weight-pass count retained.

Prefill: {command['prefill_seconds']:.6f}s; subsequent decode:
{command['decode_seconds']:.6f}s; overlapping startup wall time:
{command['startup_wall_seconds']:.6f}s. Full resident SHA verification:
{command['model_verify_ms']/1000:.6f}s; vocabulary setup:
{command['vocabulary_setup_seconds']:.6f}s (overlapped, not additive).
Every resident weight byte is checked inside the cold-call timer.

The board had already rebooted before this session. The old DMA allocation,
pinned weights and qualified v6 image were restored first; this session never
rebooted Linux. The historical timing comparison spans boots. Model loading at
boot is separate from this cold-prefill command measurement, as in v6.

Hardware: per-batch burst-loaded norm vectors; per-token rotary-row reuse;
in-place norm output II1 versus II7; RoPE II2 versus II9; same FP32 sum order.
Host control: overlapping tokenizer/hash, bounded native DMA-copy staging and
50-microsecond completion polling. Buffers derive from the model profile and
wide-load alignment is checked before NN commands. These are reusable changes;
a larger model still needs its own quantization, memory, fit and numeric proof.

One focused causal board fixture passed {len(smoke['cases'])} cases, worst error
{worst:.9g}. One real cold command was requested, with no benchmark sweep.
Routed timing and exact HLS/IP/ZIP/physical-import consistency passed before
Linux FPGA-manager deployment. The new launcher is /usr/local/bin/sysone-qwen-fpga
and the active app is {proof['fpga_app']} at {proof['clock_hz']}Hz.
The previous launcher and firmware packages are retained.

Evidence: deployment-proof.json, real-command-result.json,
hardware-block-smoke.json, routed timing under vivado/, ip-rtl-consistency.json,
hardware-source-sha256.json, completion-queue.json and board job receipts.
traffic-bound.json derives a 10.71915008s matrix-traffic-only ideal lower bound
for the unchanged workload on the current 128-bit, 100MHz weight path. Reaching
10 seconds therefore needs more weight bandwidth or fewer weight passes too.
'''
    (BUILD/'README.md').write_text(summary, encoding='utf-8')
    design = ROOT/'docs/research/2026-10-20-buffered-qwen-decoder-design.md'
    text = design.read_text(encoding='utf-8').replace(
        'Deployment and measured result: pending physical implementation.',
        f'Deployed: {seconds:.9f}s cold-prefill real command; prefill '
        f'{command["prefill_seconds"]:.6f}s, decode {command["decode_seconds"]:.6f}s. '
        f'Same prompt/generated IDs and full vocabulary; current Linux boot retained. '
        f'Target10 {"met" if seconds < 10 else "not yet met"}. See '
        'build/v2/qwen-fpga-decoder-v7/{README.md,deployment-proof.json,seal.json}.')
    design.write_text(text, encoding='utf-8')
    paths = set(p for p in BUILD.iterdir() if p.is_file())
    for directory in ['board', 'block-fixture', 'deployment']:
        paths.update(p for p in (BUILD/directory).rglob('*') if p.is_file())
    for name in ['qwen_decoder.xsa', 'routed-timing.rpt', 'routed-utilization.rpt',
                 'qwen_decoder_kr260.runs/impl_1/system_wrapper.bit']:
        paths.add(BUILD/'vivado'/name)
    for name in ['solution/syn/report/qwen_decoder_csynth.xml',
                 'solution/syn/report/qwen_decoder_csynth.rpt',
                 'solution/impl/ip/component.xml',
                 'solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h',
                 'solution/.autopilot/db/qwen_decoder.pp.0.cpp']:
        paths.add(BUILD/'hls-release'/name)
    paths.update(p for p in (ROOT/'hls/qwen_decoder_v7').iterdir() if p.is_file())
    paths.update(ROOT/'scripts/v2'/name for name in [
        'complete_qwen_fpga_v7.py', 'collect_qwen_fpga_v7.py',
        'package_qwen_fpga_v6.py', 'deploy_qwen_fpga_v6.py',
        'smoke_qwen_fpga_v6.py', 'finish_qwen_fpga_v6.py',
        'run_qwen_fpga_command_v6.py', 'qwen_fpga_board_window_ssh_v6.py'])
    paths.add(ROOT/'src/sysone/v2/qwen_fpga_runtime_v6.py')
    paths.add(design)
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}
    seal = dict(status='DEPLOYED_COLD_LATENCY_IMPROVED', date='2026-10-20',
                linux_boot_id=command['linux_boot_id'], elapsed_seconds=seconds,
                target_10_seconds_met=seconds < 10, speedup=proof['speedup'],
                comparison_method=proof['comparison_method'], old_seals=old,
                files_sha256=hashes)
    (BUILD/'seal.json').write_text(json.dumps(seal, indent=2)+'\n')
    print(json.dumps(dict(sealed_files=len(hashes), elapsed_seconds=seconds,
                          speedup=proof['speedup'], old_seals=old)))


if __name__ == '__main__':
    main()
