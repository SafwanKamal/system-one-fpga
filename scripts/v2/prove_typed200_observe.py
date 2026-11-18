"""Prove exact observation counts against original recurrence, including wrap."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default='typed200-observe-formal-v1')
    a = ap.parse_args()
    out = ROOT/'build/v2'/a.name
    out.mkdir(exist_ok=False)
    rel = out.relative_to(ROOT).as_posix()
    module = ROOT/'rtl/v2/candidates/typed200_observe/common/observed_cycle_counter.sv'
    (out/module.name).write_bytes(module.read_bytes())
    (out/'miter.sv').write_text('''module observe_formal(input clk, reset, clear, increment);
    wire [31:0] actual;
    reg [31:0] original;
    observed_cycle_counter dut(.clk(clk),.reset(reset),.clear(clear),.increment(increment),.count(actual));
    always @(posedge clk or posedge reset) begin
        if(reset) original <= 0;
        else if(clear) original <= 0;
        else if(increment) original <= original + 1'b1;
    end
    reg past_valid=0;
    always @(posedge clk) begin
        past_valid<=1;
        if(!past_valid) assume(reset);
        if(past_valid && !reset) assert(actual == original);
    end
endmodule
''')
    (out/'prove.ys').write_text(f'''read_verilog -formal -sv {rel}/{module.name} {rel}/miter.sv
prep -top observe_formal -flatten
async2sync
chformal -lower
formalff -clk2ff
dffunmap
opt_clean
sat -verify -prove-asserts -tempinduct -seq 2 -maxsteps 12 -set-assumes -set clk 1 -timeout 60 -dump_vcd {rel}/counterexample.vcd
''')
    with (out/'console.log').open('w') as log:
        r = subprocess.run(['uv', 'tool', 'run', '--from', 'yowasp-yosys==0.70.0.0.post1259',
                            'yowasp-yosys', '-Q', '-T', '-l', f'{rel}/prove.log', '-s', f'{rel}/prove.ys'],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    passed = r.returncode == 0 and 'Induction step proven: SUCCESS!' in (out/'prove.log').read_text()
    (out/'receipt.json').write_text(json.dumps({
        'passed': passed, 'exit_code': r.returncode, 'width': 32,
        'assumptions': ['first sampled edge reset', 'single sampled clock'],
        'scope': 'Arbitrary clear/increment/reset; exact modulo-2**32 original recurrence at every observed edge',
        'limits': ['not whole-encoder proof', 'not physical timing or WCET proof'],
        'source_sha256': {module.relative_to(ROOT).as_posix(): sha(module)},
        'artifact_sha256': {p.name: sha(p) for p in out.iterdir() if p.is_file()},
    }, indent=2)+'\n')
    print('PASS exact 32-bit cycle-count induction' if passed else 'NOT PROVED; preserve attempt')
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
