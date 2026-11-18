"""Require complete batch/control/boundary evidence before synthesis or routing."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "build/v2/rtl-batch-check"
ACCUMULATOR_MODE = int(sys.argv[2]) if len(sys.argv) > 2 else 0
if ACCUMULATOR_MODE not in (0, 1, 2, 3):
    raise ValueError("Unknown accumulator implementation")
ACCUMULATORS = ACCUMULATOR_MODE != 0
DOT = len(sys.argv) > 3 and sys.argv[3] == "1"


def main():
    checks = {}
    cases = [
        ("batch-wide.log", 10512, [1,2,3,4,5,12,64,128], "5359010f"),
        ("batch-l12.log", 5256, [1,2,3,4,5,12,64,128], "5359010f"),
        ("control-l12.log", 5256, [1,2,3,4,5,12,64,128], "53590109"),
        ("boundary-1024.log", 384, [1,2,3], "5359010f"),
    ]
    if ACCUMULATORS:
        cases = [(n, w, lengths, "5359011f" if n != "control-l12.log" else feature)
                 for n, w, lengths, feature in cases]
        cases.append(("one-word-head.log", 3360, [1,2,3,31,33], "5359011f"))
    if DOT:
        cases = [(n, w, lengths, "5359013f" if n != "control-l12.log" else feature)
                 for n, w, lengths, feature in cases]
    for name, words, lengths, feature in cases:
        raw = (OUT/name).read_bytes(); log = raw.decode()
        rows = re.findall(r"case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)", log)
        if [int(r[1]) for r in rows] != lengths or any(int(r[2]) or int(r[4]) or not 0<int(r[5])<=int(r[6]) for r in rows):
            raise ValueError(f"Incomplete/incorrect results: {name}")
        if f"PASS: KR260 block bit-exact, {len(lengths)} cases, {words} words compared" not in log or f"FEATURES {feature}" not in log:
            raise ValueError(f"Incomplete/profile mismatch: {name}")
        build = "20804004" if name == "boundary-1024.log" else "20803004"
        if f"BUILD register {build}" not in log:
            raise ValueError(f"Wrong hardware capacity: {name}")
        profiles = re.findall(r"profile case (\d+) counter (\d+) = (\d+)",log)
        if len(profiles) != len(lengths)*10 or len({(c,p) for c,p,v in profiles}) != len(profiles):
            raise ValueError(f"Missing performance counter checks: {name}")
        checks[name] = {"sha256":hashlib.sha256(raw).hexdigest(),"words":words,
            "encoder_clocks":[int(r[5]) for r in rows],"request_clocks":[int(r[6]) for r in rows],
            "profiles":{c:{p:int(v) for cc,p,v in profiles if cc==c} for c in sorted({c for c,p,v in profiles})}}
    for name, marker in (
        ("result-streamer.log", "PASS: result streamer 64 chunks, latency 3/4, prolonged/random backpressure"),
        ("nexys-default.log", "PASS: encoder layer bit-exact, 2 cases, 39216 words compared"),
    ):
        raw=(OUT/name).read_bytes()
        if marker not in raw.decode(): raise ValueError(f"Incomplete results: {name}")
        checks[name]={"passed":True,"sha256":hashlib.sha256(raw).hexdigest()}
    digests = {}
    for line in (OUT/"source-sha256.txt").read_text().splitlines():
        digest,name=line.split(maxsplit=1)
        digests[name]=digest
    files=list(json.loads((ROOT/"build/v2/rtl-memory-check/summary.json").read_text())["rtl_sha256"])
    files.append("rtl/v2/encoder/result_streamer.sv")
    hashes={name:digests[name] for name in files}
    if len(hashes)!=17 or any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):
        raise ValueError("Current RTL does not match the 17 tested source files")
    boundary=json.loads((OUT/"boundary-vectors/manifest.json").read_text())
    if not boundary["reference_verified"] or boundary["dims"]["hidden"]!=1024 or boundary["dims"]["ffn"]!=4096:
        raise ValueError("Missing independent 1024/4096 boundary references")
    control=checks["control-l12.log"]; batch=checks["batch-l12.log"]
    comparison={"control_request_overhead":[r-e for r,e in zip(control["request_clocks"],control["encoder_clocks"])],
                "batch_request_overhead":[r-e for r,e in zip(batch["request_clocks"],batch["encoder_clocks"])],
                "note":"Random-stall simulation; these are not board timings or worst-case bounds"}
    result={"profile":{"max_hidden":768,"mac_input_registers":1,"exp_table_in_bram":1,
                         "pipelined_uram":1,"stream_results":1,"local_query_registers":1,"perf_counters":1},
            "hardware_clock_verified":False,"checks":checks,"rtl_sha256":hashes,"comparison":comparison,
            "boundary_reference":boundary}
    if ACCUMULATORS:
        result["profile"]["local_accumulator_controls"] = ACCUMULATOR_MODE
        one_word = json.loads((OUT/"one-word-vectors/manifest.json").read_text())
        if not one_word["reference_verified"] or one_word["dims"]["hidden"] // one_word["dims"]["heads"] != 16:
            raise ValueError("Missing independent one-word-head references")
        result["one_word_reference"] = one_word
    result["profile"]["pipelined_dot"] = int(DOT)
    (OUT/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
    print("PASS: batch/control/default/1024-wide boundary regressions and counter readout")


if __name__=="__main__": main()
