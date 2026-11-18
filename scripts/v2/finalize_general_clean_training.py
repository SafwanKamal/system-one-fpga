"""Verify clean-training journals and write a bounded development report."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from sysone.v2.general_call_matching import exact_calls
from sysone.v2.general_tool_eval import BFCLPythonChecker, read_jsonl


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--evaluation-root', type=Path)
    args = ap.parse_args()
    if args.report.exists() or args.out.exists():
        raise FileExistsError('report/output already exists')
    results = {}
    expected = {}
    for family in ('encoder', 'functiongemma'):
        root = args.root/family
        manifest = load(root/'run.json')
        if manifest['stage'] != 'complete':
            raise ValueError('unfinished '+family)
        for name, sha in manifest['source_sha256'].items():
            if digest(ROOT/name) != sha:
                raise ValueError('source changed '+name)
        if digest(root/'best.pt') != manifest['best_checkpoint_sha256']:
            raise ValueError('checkpoint changed')
        splits = {name: load(root/f'{name}-cases.json') for name in ('training','selection','audit')}
        for name, rows in splits.items():
            if len(rows)!={'training':576,'selection':20,'audit':72}[name]:
                raise ValueError('unexpected finite experiment size')
            if len({r['id'] for r in rows}) != len(rows):
                raise ValueError('duplicate cases')
            if name in expected and rows != expected[name]:
                raise ValueError('different family requests')
            expected[name] = rows
        idsets = [set(r['id'].removesuffix(':deny') for r in splits[n]) for n in splits]
        if any(idsets[a]&idsets[b] for a,b in ((0,1),(0,2),(1,2))):
            raise ValueError('cross-split records')
        cases = {r['id']:r for r in splits['audit']}
        predictions = [json.loads(line) for line in (root/'audit-best-requests.jsonl').read_text().splitlines()]
        if [r['id'] for r in predictions] != list(cases):
            raise ValueError('missing/reordered audit request')
        for r in predictions:
            case = cases[r['id']]
            correct = False
            if r['valid'] and r['gold_valid'] and not r.get('error'):
                correct = exact_calls(r['calls'], case['answers'], case['tools'])
            if correct != r['correct']:
                raise ValueError('cached verdict differs')
        summary = load(root/'audit-best-summary.json')
        if summary['correct'] != sum(r['correct'] for r in predictions):
            raise ValueError('summary differs')
        history = load(root/'selection-history.json')
        selection_cases = {r['id']:r for r in splits['selection']}
        for index,item in enumerate(history):
            name = 'selection-baseline' if index==0 else f'selection-epoch-{index}'
            selection_rows = [json.loads(s) for s in (root/f'{name}-requests.jsonl').read_text().splitlines()]
            for r in selection_rows:
                case=selection_cases[r['id']]
                correct=False
                if r['valid'] and r['gold_valid'] and not r.get('error'):
                    correct=exact_calls(r['calls'],case['answers'],case['tools'])
                if correct!=r['correct']:
                    raise ValueError('strict typed selection verdict differs')
        best = history[0]
        for item in history[1:]:
            cur, prev = item['result'], best['result']
            acceptable = cur['accepted_error'] is None or prev['accepted_error'] is None or cur['accepted_error']<=prev['accepted_error']
            promote = cur['correct']>prev['correct'] and cur['correct_accepted']>=prev['correct_accepted'] and acceptable
            if item['promoted'] != promote:
                raise ValueError('selection policy differs')
            if promote:
                best = item
        if best['tag'] != manifest['best']:
            raise ValueError('selected tag differs')
        journal = [json.loads(line) for line in (root/'training.jsonl').read_text().splitlines()]
        trained = [r for r in journal if 'loss' in r]
        if len(trained) != manifest['updates']:
            raise ValueError('update count differs')
        details = dict(manifest=manifest, selection_history=history, audit=summary,
            audit_error_histogram=dict(Counter(r['error'] for r in predictions if r.get('error'))),
            audit_reference_failure_histogram=dict(Counter(r['gold_error'] for r in predictions if not r['gold_valid'])),
            audit_original=dict(requests=64, correct=sum(r['correct'] for r in predictions if not r['id'].endswith(':deny'))),
            audit_synthetic_deny=dict(requests=8, correct=sum(r['correct'] for r in predictions if r['id'].endswith(':deny'))),
            training_updates=len(trained))
        if family == 'encoder':
            prep = load(root/'preparation.json')
            jobs = load(root/'training-jobs.json')
            details['training'] = dict(effective_records=len({r['record_id'] for r in jobs}),
                prepared_jobs=prep['jobs'], argument_kinds=prep['argument_kinds'],
                failures=dict(Counter(r.get('detail',r['reason']) for r in prep['failures'])))
        else:
            details['training'] = dict(effective_records=len({r['id'] for r in trained}),
                failures_per_epoch={str(e):dict(Counter(r['profile_or_gold_error'] for r in journal if r['epoch']==e and 'profile_or_gold_error' in r)) for e in (0,1)})
        results[family] = details
    prior = load(ROOT/'build/v2/model-comparison-20261017-seal.json')
    for name, info in prior['files'].items():
        if digest(ROOT/name) != info['sha256']:
            raise ValueError('prior seal changed '+name)
    external = {}
    if args.evaluation_root:
        data=Path(results['encoder']['manifest']['arguments']['data'])
        checker_root=data/'bfcl-python-checker'
        receipt=load(checker_root/'receipt.json')
        for item in receipt['files']:
            if digest(checker_root/'bfcl_eval'/item['path'])!=item['sha256']:
                raise ValueError('pinned checker differs')
        if digest(checker_root/'bfcl_eval/constants/model_config.py')!=receipt['registry_sha256']:
            raise ValueError('local checker registry differs')
        checker=BFCLPythonChecker(checker_root)
        external_cases={r['id']:r for r in read_jsonl(data/'external-evaluation.jsonl')}
        answers=load(data/'bfcl-answer-registry.json')
        issued_ids = None
        for family in ('encoder','functiongemma'):
            parity = load(args.evaluation_root/f'{family}-parity/summary.json')
            if not parity['parity_passed'] or parity['requests']<8:
                raise ValueError('missing inference parity')
            root = args.evaluation_root/f'{family}-bfcl'
            manifest = load(root/'run.json')
            if manifest['stage']!='complete' or manifest['parent_checkpoint_sha256']!=results[family]['manifest']['best_checkpoint_sha256']:
                raise ValueError('external checkpoint differs')
            rows = [json.loads(s) for s in (root/'requests.jsonl').read_text().splitlines()]
            for row in rows:
                correct=False
                if row['valid']:
                    correct=bool(checker.score(external_cases[row['id']],row['calls'],answers[row['id']])['valid'])
                if correct!=row['correct']:
                    raise ValueError('BFCL verdict differs')
            ids = [r['id'] for r in rows]
            if issued_ids is not None and ids!=issued_ids:
                raise ValueError('different external requests')
            issued_ids=ids
            summary=load(root/'summary.json')
            if summary['requests']!=len(rows) or summary['correct']!=sum(r['correct'] for r in rows):
                raise ValueError('external summary differs')
            external[family]=summary
    output = dict(status='finite clean-data development experiment complete; no model-family selection',
        variants=results, training_requests=576, selection_requests=20, audit_requests=72,
        prior_seal_verified_files=len(prior['files']), prior_sealed_files_unchanged=True,
        board_contacted=False, paid_compute=False, blind=False, bfcl_used_for_selection=False,
        external_pilot=external,
        same_requests_both_families=True, audit_used_for_checkpoint_selection=False)
    label_audit=load(args.root/'encoder-label-audit.json')
    corrected_label_audit=load(args.root/'encoder-corrected-label-audit.json')
    if corrected_label_audit['round_trip_failures']:
        raise ValueError('corrected targets do not round trip')
    output['encoder_training_target_audit']=label_audit
    output['encoder_future_corrected_target_audit']=corrected_label_audit
    reject_correct=0
    for case in expected['audit']:
        try:reject_correct+=exact_calls([],case['answers'],case['tools'])
        except (ValueError,TypeError,KeyError):pass
    output['always_reject_audit']=dict(correct=reject_correct,requests=len(expected['audit']),correct_accepted=0)
    normalized=lambda row:re.sub(r'\s+',' ',row['query'].strip().casefold())
    output['selection_audit_overlap']=dict(
        exact_normalized_prompts=len({normalized(r) for r in expected['selection']}&{normalized(r) for r in expected['audit']}),
        schema_groups=len({r['schema_group'] for r in expected['selection']}&{r['schema_group'] for r in expected['audit']}),
        connected_components=len({r['split_component'] for r in expected['selection']}&{r['split_component'] for r in expected['audit']}))
    table = ['| Model | Selected checkpoint | Selection correct | Audit correct | Correct accepted / accepted |',
             '|---|---|---:|---:|---:|']
    for family, result in results.items():
        s=result['audit'];m=result['manifest']
        chosen=next(h['result'] for h in result['selection_history'] if h['tag']==m['best'])
        table.append(f"| {family} | {m['best']} | {chosen['correct']}/20 | {s['correct']}/72 | {s['correct_accepted']} / {s['accepted']} |")
    report = '''# General function calling: clean-data development experiment

Both models restart from their pinned official checkpoints. This is a finite CPU
development experiment, with no board access, paid compute or family winner.

'''+'\n'.join(table)+'''

Initial selection scores were 0/20 for the encoder's fresh heads and 9/20 for
official FunctionGemma. Both retained epoch 1 after epoch 2 tied. These selection
improvements are not paired evidence of improvement on the later audit.

The encoder starts with new random extraction heads. FunctionGemma already has
function-calling instruction training; initializations and representational
limits differ. Both update their final two transformer blocks for two epochs on
the same 512 original xLAM records plus 64 explicit no-action requests. They have
different learning rates and training jobs; this is not equal-compute training.
Encoder heads use a higher learning rate. Maximums are eight tools and four calls;
encoder passes allow 256 tokens, while generator context/output allow 2048/256.
The encoder remains extractive: values requiring rewriting can be unrepresentable.
The clean source split is general-tool-data-v1: xLAM revision
26d14ebfe18b1f7b524bd39b404b50af5dc97866 and BFCL revision
6ea57973c7a6097fd7c5915698c54c17c5b1b6c8. Five exact normalized BFCL prompts were
excluded before splitting. Train/development share no exact normalized prompts
or complete schema sets; individual tools and paraphrases can overlap. Both
datasets are public, and overlap with official model pretraining is unknown.

Twenty development requests select checkpoints, including four synthetic denials.
Promotion requires strictly more complete correct responses, at least as many
correct accepted commands, and no higher observed accepted error; ties retain
the earlier checkpoint. The separate 72-request development audit contains 64
original requests and eight synthetic denials, with different denial wording.
Audit originals start at shuffled development offset 80 and are disjoint from
the selection set and earlier diagnostic audit. It is not a blind or independent
external test. Checkpoint choice precedes the audit; results must not be used to
claim a family winner. BFCL did not affect training or checkpoint selection.
Selection and audit have no exact normalized prompt overlap, but share four
complete-schema/connected components. This is record-disjoint development
evaluation, not a schema-held-out test. The successor partition helper excludes
all previously inspected prefix components for its future audit.

Complete call multisets are scored with typed JSON arguments and multiplicity;
call order is ignored, and int/float equivalence applies only to number schemas.
All issued audit requests remain in denominators, including reference/profile
failures. A text refusal is nonactionable, not evidence of a correct clarification.
No tools are executed. Timing includes failures and overlapped CPU workloads;
it does not establish A53 performance, a deadline bound, energy or board speedup.

The first clean-training attempt (v2) was stopped after detecting unsupported
Python-style annotations in 207 of 576 training records. Its journals and partial
checkpoints remain diagnostic artifacts; no final audit is claimed. The v3
adapter recognizes optional scalar and nested List annotations without evaluating
expressions, coercing reference values or turning unknown types into any. Optional
means omission is permitted, not nullable. Tuples, unions, callables and other
unsupported declarations remain unsupported. Declared defaults are preserved.
The adapter reduces training reference-validation failures from 218 to 27; two
additional encoder jobs exceed its token limit. Detailed effective training
counts, failures, selection history and audit strata are in comparison.json.

An additional target audit found 37 of 1,115 encoder span labels did not decode
to the exact typed reference, all due to case differences. The reported encoder
weights were trained with those labels and remain diagnostic. A successor target
builder repairs those 37 targets: 31 find an exact alternate span and six become
unrepresentable. All 1,109 corrected span targets pass an actual decoder round
trip. These corrected targets are prepared for future training; the reported
models and predictions were not changed. Future training must use
general_encoder_targets.prepare_checked_jobs and general_call_matching.exact_calls.
The final verifier rechecks every selection and audit verdict with the latter,
which avoids lossy conversion of large integers to float; no cached verdict
is silently carried into the report.
The prepared successor runner is train_general_comparison_v4.py. It uses these
checked labels and matcher, with audit offset 144 by default and all earlier
prefix components excluded from its audit. It has not been
trained in this continuation; v3 weights must not be described as label-corrected.

Previous pilot sources, checkpoints and artifacts retain their original hashes.
The existing calibrated MiniLM/R5/PL deployment is untouched. The stronger-encoder
H768 ABI and FunctionGemma PL path remain unqualified; these host results must
not be deployed using the current H384 firmware/module ABI.

Next work remains adequate training and development calibration, the declared
full external evaluation and new human tests, followed by quantization and
separate qualification of both R5-controlled FPGA paths with Linux running.
'''
    report+=f'\nAlways rejecting scores {reject_correct}/72 on the same audit, with zero correct accepted commands.\n'
    if external:
        report+='\nThe separate frozen-checkpoint BFCL pilot repeats the same 25 public cases used\nin the earlier pilot, after eight saved-audit predictions per model pass adapter\nparity. It uses the pinned upstream checker, retains all failures, and does not\nselect checkpoints. This is not the full 1,240-request external evaluation or a\nblind test. The larger encoder per-pass token budget also differs from the old\n128-token pilot.\n\n'
        report+='| Model | BFCL complete correct | Correct accepted / accepted |\n|---|---:|---:|\n'
        for family,s in external.items():
            report+=f"| {family} | {s['correct']}/{s['requests']} | {s['correct_accepted']} / {s['accepted']} |\n"
        report+='\nThe earlier official FunctionGemma FP32 pilot scored 11/25 on these same public\ncase IDs. Its reference remains preserved. The current tuned 8/25 provides no\nevidence of improved external capability despite its stronger xLAM development\nscore. Adapter versions differ, so the historical baseline is not a matched new\nrerun. Retain the official checkpoint and investigate transfer before deployment.\n'
    args.out.mkdir(parents=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(report,encoding='utf-8')
    (args.out/'comparison.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    handoff=ROOT/'HANDOFF.md'
    before=handoff.read_bytes()
    (args.out/'HANDOFF.before-prefix.md').write_bytes(before)
    prefix=f'''# Current continuation — general tool/function calling, 2026-10-17

## New-chat start here (clean training complete; checked-target successor prepared)

User domain remains GENERAL TOOL/FUNCTION CALLING. The goal remains a stronger
encoder versus FunctionGemma, eventually BOTH with R5-controlled FPGA inference
and Linux running, then a checked typed terminal result by D. No family winner,
adequate full training, full external evaluation or new board qualification is
claimed. Read `{args.report.as_posix()}` and
`{args.out.as_posix()}/comparison.json` first.

Finite clean-split v3 training is COMPLETE under
`{args.root.as_posix()}/encoder` and `/functiongemma`. Both restart their pinned
official checkpoints; same 512 xLAM originals + 64 synthetic explicit denials,
two epochs, final 2 transformer blocks. Encoder updates 774; generator 1098.
These are issued requests; effective training counts/failures are in the report.
Dev-only selection 20 requests (16 original + 4 denials); separate audit 72
(64 original + 8 denials), original shuffled dev offset 80. No train/selection/audit
record overlap; different denial wording families. This is NOT a blind test.
Selection/audit share four complete-schema components but no exact normalized
prompts. Future v4 audit excludes all components from the inspected dev prefix.
Both retain epoch 1 because epoch 2 tied. Encoder selection 5/20, audit
{results['encoder']['audit']['correct']}/72, correct accepted
{results['encoder']['audit']['correct_accepted']}/{results['encoder']['audit']['accepted']}.
FunctionGemma selection 14/20, audit {results['functiongemma']['audit']['correct']}/72,
correct accepted {results['functiongemma']['audit']['correct_accepted']}/{results['functiongemma']['audit']['accepted']}.
Always-Reject gets {reject_correct}/72. Incorrect accepted calls remain a material
problem. Do not equate denials with accepted-command capability or clarification.

The stopped v2 clean-training attempt is diagnostic only: 207 annotations such
as str,optional were unsupported. Journals/partial checkpoints remain under
build/v2/general-tool-clean-training-v2; no final audit claimed. The v3
general_schema_annotations adapter lowers record reference failures 218 to 27;
unknown types and invalid values still fail. Optional is not nullable.

IMPORTANT ENCODER TARGET FIX: v3 still trained on 37 span targets that fail an
exact value round trip (case changes). The audit and corrected preparation are
in the v3 root. Successor src/sysone/v2/general_encoder_targets.py repairs 37
targets (31 exact alternate spans, 6 unrepresentable); all 1109 corrected span
targets round trip exactly. Reported v3 weights/predictions were NOT changed.
Use scripts/v2/train_general_comparison_v4.py for future training: checked
targets, general_call_matching exact matcher (no lossy large-int float cast),
default audit offset 144 to avoid the prior audit. v4 CLI/compile and target
preparation verified; NO v4 model training was launched. Do not call v3 weights
label-corrected. Use adequate data/training and development calibration next.

Evaluation-only adapter: scripts/v2/evaluate_general_clean.py supports partial
checkpoints, audit parity, and BFCL (--per-category 0 means all 1,240). Existing
{args.evaluation_root.as_posix() if args.evaluation_root else 'no external evaluation'}/ contains
8-request parity checks and repeated 25-case BFCL pilots, NOT the full benchmark.
All failures remain in denominators; BFCL checker/registry receipt verified and
verdicts rescored. Small public/reused pilots cannot select a model family.
Encoder 256 per-pass vs generator 2048 context/256 output, max 8 tools/4 calls; different
compute budgets. No A53 speed, energy, WCET or hardware timing result is claimed.

33 relevant tests pass. The prior {len(prior['files'])}-file artifact seal was
verified unchanged; new seal is `{args.out.as_posix()}/seal.json`. Preserve all
sealed sources/artifacts. HANDOFF itself is deliberately mutable, with this
prefix and its prior bytes saved separately. No model/evaluation job remains
running after this continuation. No commit/push or automation was created.

OPERATIONAL: NO BOARD COMMANDS OR CHANGES were made. Preserve calibrated MiniLM
PL/model/R5 deployment; JTAG/hw_server/XSDB/cs_server stay STOPPED and Linux stays
running. No raw PS/RPU probes, power cycle, stock restore, module unload or
dashboard restart. H768 image ABI/buffer relocation and FunctionGemma PL port
remain unqualified. Never load through the current H384 deployment ABI.
Hugging Face access works; never print credentials or request tokens in chat.
No paid compute was authorized or used. Host CPU-only Torch remains the working
resource; the earlier optional GPU/resource question does not block local work.

---

'''
    prefix_bytes=prefix.encode('utf-8')
    (args.out/'handoff-prefix.md').write_bytes(prefix_bytes)
    handoff.write_bytes(prefix_bytes+before)
    paths=list(args.root.rglob('*'))+[args.report,Path(__file__),ROOT/'src/sysone/v2/general_training_v2.py',ROOT/'src/sysone/v2/general_schema_annotations.py',ROOT/'scripts/v2/train_general_comparison_v2.py',ROOT/'scripts/v2/train_general_comparison_v3.py',ROOT/'tests/test_general_training_v2.py',ROOT/'tests/test_general_schema_annotations.py',args.out/'comparison.json']
    paths += [ROOT/'src/sysone/v2/general_clean_inference.py', ROOT/'scripts/v2/evaluate_general_clean.py']
    paths += [ROOT/'tests/test_general_clean_inference.py']
    paths += [ROOT/'src/sysone/v2/general_call_matching.py', ROOT/'tests/test_general_call_matching.py']
    paths += [ROOT/'src/sysone/v2/general_encoder_targets.py', ROOT/'tests/test_general_encoder_targets.py',ROOT/'scripts/v2/audit_general_encoder_labels.py']
    paths += [ROOT/'scripts/v2/train_general_comparison_v4.py']
    paths += [ROOT/'src/sysone/v2/general_clean_partitions.py',ROOT/'tests/test_general_clean_partitions.py']
    paths += [args.out/'HANDOFF.before-prefix.md', args.out/'handoff-prefix.md']
    paths += list((ROOT/'build/v2/general-tool-clean-training-v2').rglob('*'))
    if args.evaluation_root:
        paths += list(args.evaluation_root.rglob('*'))
        paths += [checker_root/'receipt.json']
        paths += list((checker_root/'bfcl_eval').rglob('*.py'))+[checker_root/'LICENSE']
    files={str(p.relative_to(ROOT) if p.is_absolute() else p):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in paths if p.is_file()}
    (args.out/'seal.json').write_text(json.dumps(dict(observed_utc=datetime.now(timezone.utc).isoformat(),files=files,files_count=len(files)),indent=2)+'\n')
    print(json.dumps(dict(report=str(args.report),results={k:dict(best=v['manifest']['best'],audit=v['audit']) for k,v in results.items()})))


if __name__ == '__main__':
    main()
