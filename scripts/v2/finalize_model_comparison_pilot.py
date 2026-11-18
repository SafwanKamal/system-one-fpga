"""Validate finite pilot journals and publish a candid, non-selection report."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_tool_eval import read_jsonl,BFCLPythonChecker
from sysone.v2.command_task import percentile

VARIANTS={
    'BERT extraction FP32 (legacy pilot)':'bert-base-cpu-v2',
    'BERT dynamic INT8':'bert-base-dynamic-int8-v3',
    'BERT FPGA arithmetic, host simulation':'bert-base-fpga-integer-v4',
    'FunctionGemma official FP32':'functiongemma-base-cpu-v0',
    'FunctionGemma 128-record pilot FP32':'functiongemma-cpu-v2',
    'FunctionGemma pilot dynamic INT8':'functiongemma-dynamic-int8-v3',
}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def wilson(k,n):
    z=1.959963984540054
    p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [center-half,center+half]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--clean-data',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    if args.report.exists():
        raise FileExistsError(args.report)
    checker=BFCLPythonChecker(args.root/'bfcl-python-checker')
    cases={r['id']:r for r in read_jsonl(args.root/'external-evaluation.jsonl')}
    answers=load(args.root/'bfcl-answer-registry.json')
    expected=None;results={}
    for label,name in VARIANTS.items():
        run=load(args.root/name/'run.json')
        if run['stage']!='complete':
            raise ValueError('unfinished run '+name)
        rows=read_jsonl(args.root/name/'requests.jsonl')
        ids={r['id'] for r in rows}
        if len(ids)!=len(rows) or len(rows)!=25:
            raise ValueError('missing/duplicate pilot requests')
        if expected is None:
            expected=ids
        if ids!=expected:
            raise ValueError('different pilot requests')
        for row in rows:
            correct=False if row.get('error') else bool(checker.score(cases[row['id']],row.get('calls',[]),answers[row['id']])['valid'])
            if correct!=row['correct']:
                raise ValueError('cached BFCL verdict differs')
        summary=load(args.root/name/'summary.json')
        if sum(r['correct'] for r in rows)!=summary['correct']:
            raise ValueError('summary differs from journal')
        accepted=[r for r in rows if r['output']['outcome']=='Accepted']
        results[label]=dict(run_directory=name,summary=summary,
            accuracy_wilson95=wilson(summary['correct'],25),
            accepted_requests=len(accepted),wrong_accepted=sum(not r['correct'] for r in accepted),
            errors=sum(bool(r.get('error')) for r in rows),
            model_memory=run.get('memory_at_end'),
            load_seconds=run.get('load_seconds'),
            prefill_first_ms={f'p{q}':percentile([r['prefill_and_first_token_ms'] for r in rows if 'prefill_and_first_token_ms' in r],q/100) for q in (50,95,99)},
            decode_after_first_ms={f'p{q}':percentile([r['decode_after_first_ms'] for r in rows if 'decode_after_first_ms' in r],q/100) for q in (50,95,99)})
    bert_ids=load(args.root/'bert-base-cpu-v2/selected-training.json')['ids']
    gen_ids=load(args.root/'functiongemma-cpu-v1/selected-training.json')['ids']
    if bert_ids!=gen_ids or len(bert_ids)!=128:
        raise ValueError('different original training records')
    parent=hashlib.sha256((args.root/'functiongemma-cpu-v1/last-layer.pt').read_bytes()).hexdigest()
    for name in ('functiongemma-cpu-v2','functiongemma-dynamic-int8-v3'):
        if load(args.root/name/'run.json')['parent_checkpoint_sha256']!=parent:
            raise ValueError('generator quantization weights differ')
    parent=hashlib.sha256((args.root/'bert-base-cpu-v2/checkpoint.pt').read_bytes()).hexdigest()
    for name in ('bert-base-dynamic-int8-v3','bert-base-fpga-integer-v4'):
        if load(args.root/name/'run.json')['parent_checkpoint_sha256']!=parent:
            raise ValueError('encoder quantization weights differ')
    prior=set(bert_ids)
    migration={split:sum(r['id'] in prior for r in read_jsonl(args.clean_data/f'{split}.jsonl'))
               for split in ('train','dev','schema-heldout-diagnostic')}
    prep=load(args.root/'bert-base-cpu-v2/training-preparation.json')
    bert_train=load(args.root/'bert-base-cpu-v2/run.json')
    gen_train=load(args.root/'functiongemma-cpu-v1/run.json')
    qualification=load(args.root/'bert-base-fpga-integer-v4/integer-qualification.json')
    clean=load(args.clean_data/'manifest.json')
    output=dict(status='finite CPU pilot complete; base selection and both board ports NOT complete',
        user_domain='general tool/function calling',requests_per_variant=25,variants=results,
        identical_training_record_ids=True,training_budget=dict(
            bert=dict(records=128,steps=bert_train['steps'],epochs=2,trainable_parameters=bert_train['trainable_parameters'],
                      seconds=bert_train['training_seconds'],prepared_jobs=prep['jobs'],profile_failed_jobs=len(prep['profile_failures']),argument_kinds=prep['argument_target_kinds']),
            functiongemma=dict(records=128,steps=gen_train['updates'],epochs=1,trainable_parameters=gen_train['trainable_parameters'],seconds=gen_train['training_seconds'])),
        prior_pilot_records_in_clean_splits=migration,clean_data=str(args.clean_data),
        integer_qualification=qualification,not_blind=True,not_board_results=True,
        no_base_winner=True,no_paid_compute=True,no_board_commands=True,
        latency_caveat='Some CPU runs overlapped. Includes early failures. No matched-quality speedup, A53 speed, energy or WCET claim.',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (args.out/'comparison.json').write_text(json.dumps(output,indent=2)+'\n')
    table=['| Variant | Complete correct | Accepted / wrong accepted | Argument F1 | p50 / p95 / p99 ms |',
           '|---|---:|---:|---:|---:|']
    for label,r in results.items():
        s=r['summary'];lat=s['resident_latency_ms']
        table.append(f"| {label} | {s['correct']}/25 | {r['accepted_requests']} / {r['wrong_accepted']} | {s['argument_micro_f1']:.3f} | {lat['p50']:.1f} / {lat['p95']:.1f} / {lat['p99']:.1f} |")
    text=f'''# General tool/function calling: first software pilot

2026-10-17. **Pipeline evidence, not base-model selection or board qualification.**
The user selected general tool/function calling. The earlier maintenance task is
retained only as a diagnostic. Neither candidate is ready for an accepted-command
deployment on the evidence below. No winner is selected.

## Frozen sources and task

Encoder: `google-bert/bert-base-uncased` at
`86b5e0934494bd15c9632b12f734a8a67f723594`. BERT-base was chosen as a concrete
H768/head64 encoder candidate compatible with the existing operator family,
rather than assuming a ModernBERT port. This does not establish better task
quality than MiniLM or the best encoder. Its extraction heads start untrained.
FunctionGemma: `google/functiongemma-270m-it` at
`39eccb091651513a5dfb56892d3714c1b5b8276c`. Both official checkpoints and
tokenizers are downloaded and hashed in the maintenance pilot inventory.

Official xLAM source revision: `26d14ebfe18b1f7b524bd39b404b50af5dc97866`;
BFCL source revision: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`.
Prepared 1,240 external BFCL requests: 400 simple Python, 200 multiple,
200 parallel, 200 parallel-multiple and 240 irrelevant requests. Five exact
normalized BFCL prompt matches were excluded from the xLAM pool before training.
Public benchmark/pretraining and semantic-paraphrase overlap remain unknown.

The pilot issues five requests per category, seed 20261017, preserving all 25
requests for each variant, errors, proposals, raw generator text, timings and
configuration/checkpoint hashes. No generated API request is executed.
The shared software outcome is Accepted(calls), Clarify, Reject, Deadline or
Fault, with no actionable payload for failures. This JSON representation has
not been integrated into the deployed typed-result ABI.

The local evaluator imports pinned, unmodified upstream BFCL Python checker
functions with a small local model-registry adapter, no provider handlers and
no function-name rewriting. Positive/negative and parallel-call tests pass.
It evaluates whole calls and argument alternatives, including order-independent
parallel matching. This is not a leaderboard submission. Argument F1 is a
separate diagnostic with greedy same-name pairing. BFCL does not validate our
clarification reason, future conditional plans, or deadline contract.

## Observed results

{chr(10).join(table)}

An always-reject baseline is 5/25 on this balanced pilot. The encoder has zero
correct accepted calls; its correct cases are nonactionable irrelevant outcomes.
The dynamic-INT8 generator also has zero correct accepted calls. Parser validity
and typed refusal do not establish command understanding. Fine-tuning 128 records
did not improve FunctionGemma over its untouched checkpoint here.

These are small, deliberately incomplete software pilots. Both receive the same
128 issued xLAM records and tool catalog, but their adaptation budgets and views
differ. BERT trains the final two blocks plus count/kind/span heads for two epochs:
{bert_train['steps']} updates, {bert_train['training_seconds']:.1f} seconds,
{prep['jobs']} prepared jobs and {len(prep['profile_failures'])} preserved input-profile
failures. FunctionGemma trains its final block for one epoch: {gen_train['updates']}
updates, {gen_train['training_seconds']:.1f} seconds. The generator already has
function-calling pretraining; BERT has no pretrained QA head in this pilot.
These budgets cannot support a family-level capability conclusion.

The recorded encoder is an extractive prototype: at most two calls per tool,
four total, eight tools, and 128 tokens per schema-conditioned pass. It reads a
tool description and parameter signatures for count prediction and a selected
parameter description for extraction. It cannot freely rewrite arbitrary
argument strings; {prep['argument_target_kinds'].get('unrepresentable',0)} training
argument targets were labeled unrepresentable. The generator receives the full
schema, permits four calls, uses a 2,048-token software profile and 256 output
tokens, with dense 262,144-row vocabulary projection. **These pilot profiles
are not the final matched-capability experiment.** The latest encoder source
supports four calls per tool for new training and retains legacy checkpoint caps.

CPU dynamic INT8 quantizes Linear operators; embeddings and the generator
vocabulary head remain FP32. It is not the FPGA integer format or a W4 image.
The full comparison JSON includes Wilson intervals, p50/p95/p99 prefill/decode,
whole-process memory observations, startup load timings and every denominator.
The reported load timer excludes Python/framework import and is not cold process
startup. Some runs overlapped on the host. Timings include early failures and
cannot support a matched-quality speedup. No A53 measurement, measured energy,
successful-inference WCET, or on-board comparison has been obtained.

## Integer-path progress, kept offline

Reused existing FloatEncoder, IntEncoder, image compiler and ImageMachine.
Paired token-type embeddings would be lost by the current constant-type0
embedding path. The adapter explicitly folds type1-type0 into a second bank of
word rows: `hardware_id = tokenizer_id + token_type_id * 30522`.
The derived vocabulary is 61,044 rows and fits uint16 IDs. This is a derived
layout with its own hashes, not an unchanged official checkpoint file.

Two float fixtures match the original paired Torch encoder within
{max(c['max_abs_error'] for c in qualification['float_type_fold_checks']):.3g}
maximum absolute hidden error (declared tolerance 0.001). Two packed-image
fixtures exactly match {sum(c['hidden_elements'] for c in qualification['exact_image_checks']):,}
hidden codes and {sum(c['integer_logits'] for c in qualification['exact_image_checks'])}
integer logits against the integer reference. This narrow check does not qualify
all shapes or real hardware. CLS count/kind and per-token span heads are retained.

The general-task candidate image is {qualification['image_bytes']:,} bytes,
SHA256 `{qualification['image_sha256']}`. Its proposed token IDs, hidden output
and mailbox are {qualification['proposed_layout']['ids']},
{qualification['proposed_layout']['hidden']}, {qualification['proposed_layout']['mailbox']}.
The proposal fits 256 MiB but overlaps the current fixed-buffer layout.
It must never be loaded with the deployed H384 firmware/module/client ABI.
No hardware image, model, firmware or clock was changed.

FunctionGemma still needs head256 attention, 32-bit token IDs, causal/KV state,
its normalization/gating and vocabulary projection implementation plus a
qualified numerical/resource layout. R5 must remain in control in the production
PL path, with Linux running. A later A53-only run must be labeled separately.

## Corrected data for the next training run

The original whole-schema-set split had 170 exact normalized train/dev prompt
overlaps, 180 train/diagnostic and 46 dev/diagnostic. Those development files
were never used to fit or select the current pilot. They are preserved.
The corrected data at `{args.clean_data.as_posix()}` groups connected components
sharing an exact normalized prompt OR an identical complete tool-schema set.
Its counts are {clean['split_counts']['train']:,} train,
{clean['split_counts']['dev']:,} dev and
{clean['split_counts']['schema-heldout-diagnostic']:,} diagnostic, with zero
cross-split exact prompt and full-schema-set overlaps. Individual tool identities
and semantic paraphrases can still overlap; this is not an independent human
blind test. Split sizes follow components, not exact 80/10/10 proportions.

Of the 128 records used by the old pilot, migration is {migration}.
**Restart future clean-split training from the original official checkpoints**;
warming from these pilot weights would contaminate some clean dev/diagnostic
records. Do not relabel these old results as clean-split results.

## Continuation

1. Use corrected data, a matched four-call profile and adequate task training.
   Improve encoder value decoding/initialization and generator adaptation on
   development data; keep the original generator as a reference. The resource
   question about CPU versus an existing GPU remains optional; no paid compute
   has been authorized or used.
2. Evaluate the full declared external subset and a separately authored human
   test including negation, missing arguments, corrections and conditional or
   composed requests. Report failures and retained coverage, not intent accuracy.
   Freeze choices before a genuinely blind test; add confidence calibration on
   separate data. The pilot is not grounds to drop either candidate.
3. Qualify actual deployment quantization, not just dynamic CPU INT8. Keep both
   deployment paths as goals, with independently qualified images, R5 control
   and Linux alive. Extend firmware/layouts and decoder operators explicitly.
   Integrate the existing typed deadline/result RTL rather than replacing it.
4. Obtain tuned A53 baselines, board startup/resident distributions, generator
   prefill/decode/full completion and energy only with real instrumentation.
   The existing calibrated MiniLM regression artifacts remain preserved; no new
   MiniLM regression or board state check was performed in this session.

Earlier maintenance artifacts, a failed 28-section image compile, the corrected
combined-head compile, the generator end-of-turn stopping error and superseded
CPU preparations are retained. The long maintenance-specific generator run was
stopped after the user chose general calling, with its completed-step journal
preserved. All finite final pilot variants above are complete. No board commands,
JTAG tools, power cycles, commit, push, recurring automation or paid compute were used.

Sources: [official FunctionGemma](https://huggingface.co/google/functiongemma-270m-it),
[official BERT](https://huggingface.co/google-bert/bert-base-uncased),
[official xLAM dataset](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k),
[pinned BFCL source](https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard).
'''
    args.report.write_text(text,encoding='utf-8')
    print(json.dumps(dict(report=str(args.report),comparison=str(args.out/'comparison.json'),variants=len(results),requests_each=25),indent=2))


if __name__=='__main__':
    main()
