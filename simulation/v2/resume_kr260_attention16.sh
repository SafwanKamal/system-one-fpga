#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/rtl-attention16-check"
test ! -e "$output/completion-status.json" || { echo 'Review existing completion first' >&2; exit 1; }
stage=$(cat "$output/snapshot.txt")
test -x "$stage/simulation/v2/obj_attention16/kr260_encoder_tb"
work=$(mktemp -d /var/tmp/sysone-attention16-resume.XXXXXX)
mkdir -p "$work/vectors/kr260"
cp "$stage/simulation/v2/obj_attention16/kr260_encoder_tb" "$work/sim"
printf '%s\n' "$work" > "$output/resume-work.txt"
sha256sum "$work/sim" > "$output/resume-binary-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
grep -q 'PASS: KR260 block bit-exact, 8 cases' "$output/wide.log"
cp "$output/l12.log" "$output/l12-interrupted.log"
cp -r "$repo/simulation/v2/vectors/kr260/." "$work/vectors/kr260/"
python3 - "$output" "$repo" "$work" <<'PY'
from pathlib import Path
import sys,re,shutil,json
out,repo,work=map(Path,sys.argv[1:])
text=(out/'l12-interrupted.log').read_text()
pattern=r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)'
rows=list(re.finditer(pattern,text)); count=len(rows)
assert 0<count<8 and [int(m[1]) for m in rows]==list(range(count))
assert all(m[3]=='0' and m[5]=='0' for m in rows)
source=repo/'simulation/v2/vectors/kr260'
total,base=(source/'cases.txt').read_text().split(); assert int(total)==8
for i in range(count,8): shutil.copyfile(source/f'case_{i}.txt',work/'vectors/kr260'/f'case_{i-count}.txt')
(work/'vectors/kr260/cases.txt').write_text(f'{8-count} {base}\n')
(out/'l12-resume-prefix.txt').write_text(text[:rows[-1].end()]+'\n')
(out/'resume-metadata.json').write_text(json.dumps({'completed_wide_cases_preserved':8,'completed_l12_cases_preserved':count,'cause':'WSL restarted; cause unknown','recompiled':False},indent=2))
PY
cd "$work"
./sim | tee "$output/l12-remainder.log"
python3 - "$output" <<'PY'
from pathlib import Path
import sys,json,re
out=Path(sys.argv[1]);count=json.loads((out/'resume-metadata.json').read_text())['completed_l12_cases_preserved']
tail=(out/'l12-remainder.log').read_text()
assert f'PASS: KR260 block bit-exact, {8-count} cases' in tail
tail=re.sub(r'case (\d+)',lambda m:f'case {int(m[1])+count}',tail)
(out/'l12.log').write_text((out/'l12-resume-prefix.txt').read_text()+tail)
PY
for profile in one-word boundary h1024 partial; do
    case "$profile" in
        one-word) vectors="$repo/build/v2/rtl-batch3-check/one-word-vectors" ;;
        boundary) vectors="$repo/build/v2/rtl-batch-check/boundary-vectors" ;;
        h1024) vectors="$repo/build/v2/kr260-dot7-h1024-eight-vectors" ;;
        partial) vectors="$repo/build/v2/drain-partial-vectors" ;;
    esac
    test ! -e "$output/$profile.log" || { echo 'Preserve existing profile; review first' >&2; exit 1; }
    cp -r "$vectors/." vectors/kr260/
    ./sim | tee "$output/$profile.log"
done
python3 - "$output" "$repo" <<'PY'
from pathlib import Path
import sys,shutil,json
out,repo=map(Path,sys.argv[1:]);base=repo/'build/v2/rtl-source-row-bram-parameter-check'
def hashes(folder):
    return {name:digest for digest,name in (line.split(maxsplit=1) for line in (folder/'source-sha256.txt').read_text().splitlines())}
a,b=hashes(out),hashes(base)
names=[n for n in a if n.startswith('rtl/v2/encoder/') or n in ('simulation/v2/encoder_layer_tb.sv','simulation/v2/memory_port_model.sv')]
assert all(a[n]==b[n] for n in names), 'Default engine sources changed; cannot reuse proof'
assert 'PASS: encoder layer bit-exact, 2 cases' in (base/'nexys-default.log').read_text()
shutil.copyfile(base/'nexys-default.log',out/'nexys-default.log')
(out/'nexys-proof-reuse.json').write_text(json.dumps({'source':str(base),'byte_identical_default_dependencies':names,'reused_cases':2,'reason':'Only private KR260 wrapper lane setting differs; Nexys dependencies unchanged'},indent=2))
PY
