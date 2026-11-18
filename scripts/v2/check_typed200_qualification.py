"""Build an offline ABI qualification kit against frozen firmware, no target IO."""
from pathlib import Path
from dataclasses import asdict
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from sysone.v2.ddr_image import ImageMachine
from sysone.v2.typed200_capture import ExpectedCapture


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--name', required=True)
    args = ap.parse_args()
    if not re.fullmatch(r'typed200-qualification-host-v[0-9]+', args.name):
        raise ValueError('Use a distinct typed200-qualification-host-vN name')
    prior_path = ROOT/'docs/research/2026-10-15-typed200-timing-continuation-validation.json'
    prior = json.loads(prior_path.read_text())
    preserved = {}
    for key in ('preserved_sha256', 'review_sha256', 'new_source_and_report_sha256'):
        for name, expected in prior[key].items():
            actual = sha(ROOT/name)
            if actual != expected:
                raise ValueError(f'Prior sealed file changed: {name}')
            preserved[name] = actual
    out = ROOT/'build/v2'/args.name
    out.mkdir(exist_ok=False)
    rel = out.relative_to(ROOT).as_posix()
    commands = []

    def run(command, log, *, expected_exit=0, env=None):
        r = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out/log).write_bytes(r.stdout)
        commands.append({'argv': command, 'returncode': r.returncode, 'log': log})
        if r.returncode != expected_exit:
            raise RuntimeError(f'Failed {log}; attempt preserved')
        return r

    wslroot = '/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    prefix = ['wsl', '-d', 'Ubuntu-24.04', '--cd', wslroot, '--']
    run([*prefix, 'gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
         '-fno-fast-math', '-ffp-contract=off', '-fsanitize=address,undefined',
         '-fno-sanitize-recover=all', 'firmware/typed_intent/typed_intent.c',
         'firmware/typed200_v2/typed200.c', 'firmware/typed200_r5/service.c',
         'firmware/typed200_qualification/capture_host.c', '-o', rel+'/capture-host'], 'compile.log')
    run([*prefix, rel+'/capture-host', rel], 'host-run.log')
    tools = Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env = os.environ.copy()
    env['PATH'] = 'C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
    run([str(tools/'clang.exe'), '--target=arm-none-eabi', '-mcpu=cortex-r5',
         '-mfpu=vfpv3-d16', '-mfloat-abi=hard', '-std=c11', '-O2', '-Wall', '-Wextra',
         '-Werror', '-ffreestanding', '-c', 'firmware/typed200_qualification/abi_layout.c',
         '-o', str(out/'abi-r5.o')], 'abi-r5-compile.log', env=env)
    run([str(tools/'llvm-readelf.exe'), '-h', str(out/'abi-r5.o')], 'abi-r5-object.txt', env=env)
    run([sys.executable, '-m', 'pytest', 'tests/test_typed200_capture.py', '-q',
         '--junitxml='+str(out/'pytest.xml')], 'pytest.log')

    image = ROOT/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img'
    if sha(image) != '4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb':
        raise ValueError('Frozen model image mismatch')
    machine = ImageMachine(image.read_bytes())
    logits, scales = machine.head_logits(np.zeros((2, 384), dtype=np.int8),
                                         'intent.atis', np.array([0, 1], dtype=np.uint16))
    golden_label = int(np.argmax(logits*scales))
    results = {}
    # The mock PL supplies deterministic ages; these are not measured hardware timings.
    for case, outcome, label, request, admitted in [
        ('accepted', 1, golden_label, 1, True), ('deadline', 5, 0, 1, True),
        ('fault', 4, 0, 1, True), ('cpu-invalid', 6, 0, 0, False),
        ('cpu-fault', 4, 0, 1, True)]:
        ids = (101, 30522) if case == 'cpu-invalid' else (101, 102)
        expected = ExpectedCapture(0x12345678, request, 1, 2, 0, 2, 500,
                                   admitted, outcome, label, ids)
        ep = out/f'{case}.expected.json'
        ep.write_text(json.dumps(asdict(expected), indent=2)+'\n')
        command = [sys.executable, 'scripts/v2/check_typed200_capture.py',
                   '--expected', str(ep), '--shared', str(out/f'{case}.shared.bin'),
                   '--output', str(out/f'{case}.report.json')]
        if case in ('accepted', 'deadline', 'fault'):
            command += ['--pl', str(out/f'{case}.pl.bin')]
        run(command, f'{case}.check.log')
        results[case] = json.loads((out/f'{case}.report.json').read_text())
    # Verify the real CLI rejects corruption without writing a success report.
    raw = bytearray((out/'accepted.shared.bin').read_bytes())
    raw[328] ^= 1
    (out/'corrupt.shared.bin').write_bytes(raw)
    run([sys.executable, 'scripts/v2/check_typed200_capture.py',
         '--expected', str(out/'accepted.expected.json'), '--shared', str(out/'corrupt.shared.bin'),
         '--pl', str(out/'accepted.pl.bin'), '--output', str(out/'corrupt.report.json')],
        'corrupt-rejected.log', expected_exit=1)
    if (out/'corrupt.report.json').exists():
        raise ValueError('Corrupt record received a success report')

    # Verify sealed inputs again after compilation/execution.
    for name, expected in preserved.items():
        if sha(ROOT/name) != expected:
            raise ValueError(f'Preservation failure after run: {name}')
    sources = [Path(__file__), ROOT/'scripts/v2/check_typed200_capture.py',
               ROOT/'src/sysone/v2/typed200_capture.py', ROOT/'tests/test_typed200_capture.py',
               ROOT/'firmware/typed200_qualification/capture_host.c',
               ROOT/'firmware/typed200_qualification/abi_layout.c']
    receipt = {'passed': True, 'capture_source': 'host_service_with_mock_pl_registers',
               'target_executed': False, 'wcet_certified': False,
               'host_and_arm_abi_compile_assertions_passed': True,
               'arm_abi_compiler_sha256': sha(tools/'clang.exe'),
               'prior_seal_sha256': sha(prior_path), 'preserved_unique_files': len(preserved),
               'preserved_sha256': preserved, 'independent_image_zero_hidden_label': golden_label,
               'results': results, 'commands': commands,
               'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
               'artifact_sha256': {p.name: sha(p) for p in out.iterdir() if p.is_file()},
               'limits': ['Mock ages are supplied, not measured',
                          'Mailbox snapshot coherence/ownership and capture provenance require target evidence',
                          'No target numerical execution, WCET or external-delivery proof']}
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS frozen service sanitizer captures, offline decoder, independent model label, negative CLI; no target execution')


if __name__ == '__main__':
    main()
