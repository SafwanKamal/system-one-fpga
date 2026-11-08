"""Verify and assemble consolidated RC1 offline; never programs the board.

Uses the pinned, already-routed v9e hardware without renaming its firmware ABI.
All old packages and evidence remain untouched. Output must be a new directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LOCK = Path('hardware/candidates/consolidated-rc1/candidate.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError('Path escapes package root: ' + name)
    return path


def verify_pipeline_ii(log, exceptions):
    pipelines = re.findall(
        r"Pipelining result : Target II = (\w+), Final II = (\d+), Depth = \d+, (?:loop|function) '([^']+)'", log)
    if not pipelines:
        raise RuntimeError('No HLS pipeline evidence')
    for target, final, loop in pipelines:
        if target != 'NA' and int(final) > int(target):
            if loop not in exceptions or int(final) > exceptions[loop]:
                raise RuntimeError('Unqualified pipeline II: ' + loop)


def verify(root=ROOT):
    lock = json.loads((root / LOCK).read_text())
    for section in ('artifacts_sha256', 'hardware_sources_sha256', 'host_sources_sha256'):
        for name, digest in lock[section].items():
            if sha(checked(root, name)) != digest:
                raise RuntimeError('Pinned input changed: ' + name)
    source = root / lock['source_package']
    hashes = json.loads((source / 'package-sha256.json').read_text())
    for name, digest in hashes.items():
        if sha(checked(source, name)) != digest:
            raise RuntimeError('Historical package changed: ' + name)
    build = json.loads((source / lock['app'] / 'build.json').read_text())
    profile = build['model_profile']
    model = json.loads((source / 'model-manifest.json').read_text())
    if profile['max_context'] != 2048 or profile['prefill_batch'] != 8:
        raise RuntimeError('Wrong compiled candidate profile')
    for key in ('hidden', 'ffn', 'q_heads', 'kv_heads', 'layers', 'vocab', 'max_context', 'head_dim'):
        if model[key] != profile[key]:
            raise RuntimeError('Model/kernel profile differs: ' + key)
    if len((source / 'rope.bin').read_bytes()) != 2048 * 512:
        raise RuntimeError('Wrong RoPE extent')
    buildroot = source.parent
    verify_pipeline_ii((buildroot / 'hls-release-console.log').read_text(errors='replace'),
                       lock['hls_ii_exceptions'])
    bit = buildroot / 'vivado/qwen_decoder_kr260.runs/impl_1/system_wrapper.bit'
    xsa = buildroot / 'vivado/qwen_decoder.xsa'
    if sha(bit) != build['bitstream_sha256'] or sha(xsa) != build['xsa_sha256']:
        raise RuntimeError('Routed bitstream/export differs')
    with zipfile.ZipFile(xsa) as archive:
        members = [n for n in archive.namelist() if n.endswith('.bit')]
        if len(members) != 1 or archive.read(members[0]) != bit.read_bytes():
            raise RuntimeError('XSA contains a different bitstream')
    timing = buildroot / 'vivado/routed-timing.rpt'
    if sha(timing) != build['routed_timing_sha256'] or 'All user specified timing constraints are met.' not in timing.read_text():
        raise RuntimeError('Routed timing not qualified')
    consistency = json.loads((buildroot / 'ip-rtl-consistency.json').read_text())
    if not consistency['passed'] or not consistency['vivado_imported_rtl_verified']:
        raise RuntimeError('HLS export/import consistency not qualified')
    if consistency['ip_archive_sha256'] != sha(buildroot / 'qwen_decoder_ip.zip'):
        raise RuntimeError('Qualified HLS export differs')
    causal = json.loads((buildroot / 'board-evidence-1/validation-summary.json').read_text())
    if not causal['smoke_passed'] or causal['smoke_cases'] != 4112:
        raise RuntimeError('Historical causal qualification absent')
    return lock, source, hashes


def assemble(output, root=ROOT):
    lock, source, hashes = verify(root)
    output = output.resolve()
    archive_path = output.with_suffix('.tar')
    if output.exists() or archive_path.exists():
        raise RuntimeError('Candidate output exists; choose a new version')
    # No parent/child overlap with historical packages or tracked source trees.
    if source.resolve().is_relative_to(output) or output.is_relative_to(source.resolve()):
        raise RuntimeError('Candidate output overlaps historical package')
    output.mkdir(parents=True)
    for name in sorted(hashes):
        if name.startswith(('src/', 'scripts/')):
            continue
        target = checked(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checked(source, name), target)
    for name in lock['host_files']:
        target = checked(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checked(root, name), target)
    # Metadata correction only; the immutable historical build.json is copied as-is.
    metadata = dict(lock, kv_cache_layout='head-major [layer][k/v][kv_head][position][128] BF16',
                    resident_service='scripts/v2/qwen_arm_service_candidate.py',
                    newly_board_qualified=False, hardware_bitstream_unchanged=True)
    (output / 'candidate.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (output / 'README.md').write_text((root / LOCK.parent / 'README.md').read_text())
    package_hashes = {p.relative_to(output).as_posix(): sha(p)
                      for p in sorted(output.rglob('*')) if p.is_file()}
    (output / 'package-sha256.json').write_text(json.dumps(package_hashes, indent=2) + '\n')
    with tarfile.open(archive_path, 'w') as archive:
        for name in [*sorted(package_hashes), 'package-sha256.json']:
            archive.add(output / name, arcname=name)
    return dict(candidate=lock['candidate'], package=str(output), archive=str(archive_path),
                archive_sha256=sha(archive_path), files=len(package_hashes),
                hardware_bitstream_unchanged=True, newly_board_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        result = assemble(args.output)
    else:
        lock, _, hashes = verify()
        result = dict(candidate=lock['candidate'], verified=True, historical_files=len(hashes))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
