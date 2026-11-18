"""Verify expanded general-tool journals, numerical references and prior seals."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_call_matching import exact_calls
from sysone.v2.general_schema_annotations import adapt_tool
from sysone.v2.general_tools import validate_calls
from sysone.v2.general_tool_eval import BFCLPythonChecker,read_jsonl,select_cases


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def sources(manifest):
    for name,sha in manifest['source_sha256'].items():
        path=Path(name)
        if not path.is_absolute():path=ROOT/path
        if digest(path)!=sha:raise ValueError('source changed '+name)


def main():
    data=ROOT/'build/v2/general-tool-data-v1'
    training=ROOT/'build/v2/general-tool-expanded-training-v4'
    evaluations=ROOT/'build/v2/general-tool-expanded-evaluation-v4'
    out=ROOT/'build/v2/general-tool-expanded-report-v4'
    report=ROOT/'docs/research/2026-10-18-general-tool-expanded-reference.md'
    if out.exists() or report.exists():raise FileExistsError('final output already exists')
    train=load(training/'encoder/run.json')
    if train['stage']!='complete':raise ValueError('encoder training incomplete')
    sources(train)
    for name,sha in train['data_sha256'].items():
        if digest(data/name)!=sha:raise ValueError('training data changed')
    if digest(training/'encoder/best.pt')!=train['best_checkpoint_sha256']:
        raise ValueError('encoder checkpoint changed')
    cases={n:load(training/f'encoder/{n}-cases.json') for n in ['training','selection','audit']}
    if [len(cases[n]) for n in cases]!=[2304,20,72]:raise ValueError('unexpected train/dev counts')
    normalize=lambda r:re.sub(r'\s+',' ',r['query'].strip().casefold())
    for a,b in [('training','selection'),('training','audit'),('selection','audit')]:
        for key in ['id','split_component']:
            if {r[key] for r in cases[a]}&{r[key] for r in cases[b]}:raise ValueError('split overlap '+key)
        if {normalize(r) for r in cases[a]}&{normalize(r) for r in cases[b]}:
            raise ValueError('prompt overlap')
    selection={r['id']:r for r in cases['selection']}
    history=load(training/'encoder/selection-history.json');chosen=history[0]
    for index,item in enumerate(history):
        name='selection-baseline' if index==0 else f'selection-epoch-{index}'
        rows=read_jsonl(training/f'encoder/{name}-requests.jsonl')
        if [r['id'] for r in rows]!=list(selection):raise ValueError('selection requests differ')
        for row in rows:
            case=selection[row['id']];correct=False
            if row['valid'] and row['gold_valid'] and not row.get('error'):
                correct=exact_calls(row['calls'],case['answers'],case['tools'])
            if correct!=row['correct']:raise ValueError('selection verdict differs')
        if sum(r['correct'] for r in rows)!=item['result']['correct']:raise ValueError('selection count differs')
        if index:
            current,previous=item['result'],chosen['result']
            acceptable=current['accepted_error'] is None or previous['accepted_error'] is None or current['accepted_error']<=previous['accepted_error']
            promote=current['correct']>previous['correct'] and current['correct_accepted']>=previous['correct_accepted'] and acceptable
            if promote!=item['promoted']:raise ValueError('selection policy differs')
            if promote:chosen=item
    if chosen['tag']!=train['best']:raise ValueError('selected checkpoint differs')
    audit_rows=read_jsonl(training/'encoder/audit-best-requests.jsonl')
    if [r['id'] for r in audit_rows]!=[r['id'] for r in cases['audit']]:raise ValueError('audit cases differ')
    for row,case in zip(audit_rows,cases['audit']):
        correct=False
        if row['valid'] and row['gold_valid'] and not row.get('error'):
            correct=exact_calls(row['calls'],case['answers'],case['tools'])
        if correct!=row['correct']:raise ValueError('audit verdict differs')
    label_audit=load(training/'encoder-label-audit.json')
    if label_audit['round_trip_failures']!=0:raise ValueError('encoder target round trip failed')
    updates=read_jsonl(training/'encoder/training.jsonl')
    if len(updates)!=train['updates'] or any('loss' not in r or not math.isfinite(r['loss']) for r in updates):raise ValueError('training updates differ')
    prep=load(training/'encoder/preparation.json')
    jobs=load(training/'encoder/training-jobs.json')
    if train['updates']!=2*((len(jobs)+7)//8):raise ValueError('epoch/update budget differs')
    cache_verification=load(training/'model-inventory-verification.json')
    for entry in cache_verification['files']:
        if digest(Path(entry['file']))!=entry['sha256']:raise ValueError('official cache changed')
    checker_root=data/'bfcl-python-checker';receipt=load(checker_root/'receipt.json')
    for item in receipt['files']:
        if digest(checker_root/'bfcl_eval'/item['path'])!=item['sha256']:raise ValueError('checker changed')
    if digest(checker_root/'bfcl_eval/constants/model_config.py')!=receipt['registry_sha256']:
        raise ValueError('checker registry changed')
    checker=BFCLPythonChecker(checker_root)
    external={r['id']:r for r in select_cases(data/'external-evaluation.jsonl',0)}
    answers=load(data/'bfcl-answer-registry.json')
    if len(external)!=1240:raise ValueError('declared external scope differs')
    results={}
    for family,directory in [('encoder','encoder-full'),('functiongemma_official','functiongemma-official-full')]:
        root=evaluations/directory;manifest=load(root/'run.json')
        if manifest['stage']!='complete':raise ValueError('external run incomplete '+family)
        sources(manifest)
        for name,sha in manifest['data_sha256'].items():
            if digest(data/name)!=sha:raise ValueError('external data changed')
        if family=='encoder' and manifest['parent_checkpoint_sha256']!=train['best_checkpoint_sha256']:
            raise ValueError('encoder external checkpoint differs')
        if family=='functiongemma_official' and (not manifest['official_reference'] or manifest['checkpoint_loaded']):
            raise ValueError('reference is not official initialization')
        rows=read_jsonl(root/'requests.jsonl')
        if len(rows)!=1240 or len({r['id'] for r in rows})!=1240 or {r['id'] for r in rows}!=set(external):
            raise ValueError('missing, duplicated or filtered external requests')
        for row in rows:
            case=external[row['id']];correct=False
            if row['valid']:
                validate_calls(row['calls'],[adapt_tool(t) for t in case['tools']])
                if row.get('error'):raise ValueError('valid result also has error')
                correct=bool(checker.score(case,row['calls'],answers[case['id']])['valid'])
            if correct!=row['correct'] or row['accepted']!=(row['valid'] and bool(row['calls'])):
                raise ValueError('external verdict or accepted flag differs')
        summary=load(root/'summary.json')
        accepted=[r for r in rows if r['accepted']]
        for key,value in dict(requests=len(rows),correct=sum(r['correct'] for r in rows),accepted=len(accepted),
            correct_accepted=sum(r['correct'] for r in accepted),wrong_accepted=sum(not r['correct'] for r in accepted)).items():
            if summary[key]!=value:raise ValueError('external summary differs '+key)
        results[family]=dict(summary=summary,manifest=manifest,
            error_histogram=dict(Counter(r['error'] for r in rows if r.get('error'))))
    enc_parity=load(evaluations/'encoder-parity/summary.json')
    batch_parity=load(evaluations/'functiongemma-batch4-parity/summary.json')
    if not enc_parity['parity_passed'] or enc_parity['requests']<8 or not batch_parity['parity_passed'] or batch_parity['requests']!=25:
        raise ValueError('evaluator parity missing')
    prefix=read_jsonl(evaluations/'functiongemma-official-bfcl/resume-prefix.jsonl')
    actual=read_jsonl(evaluations/'functiongemma-official-full/requests.jsonl')
    if len(prefix)!=527:raise ValueError('prefix count differs')
    for expected,row in zip(prefix,actual):
        stripped={k:v for k,v in row.items() if k!='source_engine'}
        if stripped!=expected:raise ValueError('completed prefix result changed')
    interruption=load(evaluations/'functiongemma-official-bfcl/administrative-interruption.json')
    original=evaluations/'functiongemma-official-bfcl/requests.jsonl'
    if digest(original)!=interruption['original_journal_sha256']:raise ValueError('original prefix journal changed')
    if sum(r['id']==interruption['in_flight_id'] for r in actual)!=1:
        raise ValueError('interrupted case not completed exactly once')
    foundations={}
    for name,folder,filename in [
        ('float_blocks','functiongemma-float-ops-v1','qualification.json'),
        ('integer_primitives','functiongemma-integer-ops-v1','qualification.json'),
        ('storage','functiongemma-storage-v2','storage-plan.json'),
        ('float_decoder','functiongemma-decoder-float-v1','qualification.json'),
        ('packed_rtl','functiongemma-packed-rtl-v2','qualification.json')]:
        value=load(ROOT/f'build/v2/{folder}/{filename}');sources(value)
        if name!='storage' and value['stage']!='complete':raise ValueError('foundation qualification incomplete')
        foundations[name]=value
    if not all(r['exact_token'] and r['hidden_pass'] and r['logits_pass'] for r in foundations['float_decoder']['checks']):
        raise ValueError('whole decoder mismatch')
    if len({r['model_sha256'] for r in foundations.values()})!=1:raise ValueError('foundation parents differ')
    rtl=foundations['packed_rtl']
    if [r['bits'] for r in rtl['checks']]!=[6,7,8] or not all(r['passed'] for r in rtl['checks']):
        raise ValueError('packed RTL simulation incomplete')
    for bits in [6,7,8]:
        for filename in [f'complete-{bits}.txt',f'utilization-{bits}.rpt',f'synthesis-timing-{bits}.rpt']:
            if not (ROOT/'build/v2/functiongemma-packed-rtl-v2/synthesis'/filename).is_file():
                raise ValueError('packed RTL isolated synthesis incomplete')
    synthesis_root=ROOT/'build/v2/functiongemma-packed-rtl-v2/synthesis'
    rtl_synthesis=dict(part='xck26-sfvc784-2LV-c',scope='isolated synthesis; no routing or timing qualification',
        source_sha256={'scripts/v2/kr260/check_packed_weight_row_ooc.tcl':digest(ROOT/'scripts/v2/kr260/check_packed_weight_row_ooc.tcl')},
        configurations=[])
    for bits in [6,7,8]:
        utilization=(synthesis_root/f'utilization-{bits}.rpt').read_text(encoding='utf-8')
        luts=int(re.search(r'\| CLB LUTs\*\s*\|\s*(\d+)',utilization).group(1))
        registers=int(re.search(r'\| CLB Registers\s*\|\s*(\d+)',utilization).group(1))
        rtl_synthesis['configurations'].append(dict(bits=bits,luts=luts,registers=registers,
            report_sha256=digest(synthesis_root/f'utilization-{bits}.rpt')))
    preflight=load(evaluations/'functiongemma-input-preflight.json');sources(preflight)
    if preflight['requests']!=1240 or preflight['requests_with_unsupported_ids']:
        raise ValueError('input preflight differs')
    prior_files={}
    for path in [ROOT/'build/v2/model-comparison-20261017-seal.json',ROOT/'build/v2/general-tool-clean-report-v3/seal.json']:
        for name,info in load(path)['files'].items():
            key=Path(name).as_posix()
            if key in prior_files and prior_files[key]['sha256']!=info['sha256']:
                raise ValueError('conflicting prior seals')
            prior_files[key]=info
    for name,info in prior_files.items():
        if digest(ROOT/name)!=info['sha256']:raise ValueError('prior seal changed '+name)
    reject=sum(r['category']=='irrelevance' for r in external.values())
    test_bytes=(training/'tests.log').read_bytes()
    test_log=test_bytes.decode('utf-16' if test_bytes.startswith(b'\xff\xfe') else 'utf-8-sig')
    if '49 passed' not in test_log:raise ValueError('required test suite result missing')
    summary=dict(status='expanded CPU reference complete; no model-family selection or FPGA qualification',
        encoder_training=dict(manifest=train,selection_history=history,audit=load(training/'encoder/audit-best-summary.json'),
            training_requests=2304,effective_records=len({r['record_id'] for r in jobs}),
            prepared_jobs=prep['jobs'],target_corrections=len(prep['target_corrections']),
            failures=dict(Counter(r.get('detail',r['reason']) for r in prep['failures'])),
            label_audit=label_audit),external=results,always_reject=dict(correct=reject,requests=1240,correct_accepted=0),
        evaluator_parity=dict(encoder=enc_parity,functiongemma_batch=batch_parity),foundations=foundations,
        packed_rtl_synthesis=rtl_synthesis,
        administrative_interruption=interruption,official_reference_completed_cases=1240,
        official_reference_total_attempts_including_administrative_interruption=1241,
        prior_sealed_files_verified=len(prior_files),prior_sealed_files_unchanged=True,
        no_family_winner=True,board_contacted=False,paid_compute=False,blind=False,
        tests=dict(passed=49,log_sha256=digest(training/'tests.log')),
        outstanding=['adequate matched task training/calibration and human blind tests','full v3 tuned generator evaluation',
            'whole-model integer calibration/quality','packed RTL integration/compiler/R5/module ABI',
            'typed call payload validation/publication and terminal-by-D integration qualification'])
    lines=['| Variant | BFCL complete correct | Correct accepted / accepted | Wrong accepted |',
        '|---|---:|---:|---:|']
    for name,value in results.items():
        s=value['summary'];lines.append(f"| {name} | {s['correct']}/1240 | {s['correct_accepted']} / {s['accepted']} | {s['wrong_accepted']} |")
    category_lines=['| Category | Encoder correct | Official FunctionGemma correct |',
        '|---|---:|---:|']
    for category in ['simple_python','multiple','parallel','parallel_multiple','irrelevance']:
        values=[results[name]['summary']['categories'][category] for name in results]
        category_lines.append(f"| {category} | {values[0]['correct']}/{values[0]['requests']} | {values[1]['correct']}/{values[1]['requests']} |")
    storage=foundations['storage'];decoder=foundations['float_decoder']
    text='''# Expanded general function-calling reference and offline port foundations

Finite CPU work only. Both models' FPGA ports, base-family selection and the
typed terminal-by-D contract remain unfinished. No board changes or paid compute.

'''+'\n'.join(lines)+f'''

Always-Reject scores {reject}/1240, with zero correct accepted commands. Results
use the pinned BFCL Python checker and all 1,240 declared requests: 400 simple,
200 multiple, 200 parallel, 200 parallel-multiple and 240 irrelevance. Every
completed failure remains in the denominator. The finalizer rescores all rows.
Correct refusals contribute to the overall score; correct accepted calls and
wrong accepted calls are reported separately above.

'''+ '\n'.join(category_lines)+f'''

These are public datasets, not a blind test or leaderboard submission; overlap
with official model pretraining is unknown. Five exact BFCL prompt overlaps
were removed from xLAM before the clean training/development split.

The encoder restarts pinned BERT-base with corrected extraction targets, using
2,048 xLAM originals plus 256 synthetic denials for two epochs. Both final
transformer blocks and the new heads train. All {label_audit['span_targets_checked']}
span targets round-trip exactly; {len(prep['target_corrections'])} targets needed correction.
Reference/profile failures are preserved in preparation and effective counts.
Twenty development requests select the checkpoint; a separate 72-request audit
excludes every schema/prompt component in the previously inspected development
prefix. There is no cross-split exact prompt or component overlap. Individual
tools/paraphrases can still overlap. Encoder selection is
{chosen['result']['correct']}/20 and the separate audit is {summary['encoder_training']['audit']['correct']}/72.
The encoder remains an extractive prototype, including unrepresentable values.

FunctionGemma here is the original official FP32 checkpoint, with no adaptation
weights loaded. This is not equal task training, compute, representations or
context exposure: encoder passes allow256 tokens versus generator2048 context
and256 output tokens, with at most8 tools and4 calls. No family winner follows.
The v3 tuned generator is preserved; its full-scope evaluation remains pending.

The reference preserves527 completed single-request results exactly and evaluates
the remaining713 in length-bucketed batches of4. All25 historical official
outputs/calls/validity/errors reproduced literally during batch qualification
(11/25 correct). One administrative in-flight interruption, parallel_67, was
recorded separately and reissued; no completed failure was retried. There are
1,240 completed case results and1,241 attempts including that interruption.
The complete interrupted trace and lineage remain available. Runtime batching
is declared; combined latency is not compared with single-request latency.
CPU work overlapped; no A53 speed, energy, DDR bound or WCET result is claimed.

The offline FunctionGemma float reference covers explicit head width256,
GQA4:1, local/global RoPE, Gemma1+weight RMS, gated tanh-GELU, all18 blocks and
shared embedding/full262,144-row vocabulary projection. Six real-weight block
fixtures pass predeclared atol0.001/rtol0.0001, including the512-token window
boundary and position8192. The whole decoder matches all {len(decoder['checks'])} greedy
tokens through the function-response marker on one authored fixture. Maximum
logit absolute error is {max(r['logits_max_abs_error'] for r in decoder['checks']):.6g}; this is one-fixture
numerical evidence, not general task accuracy or integer/RTL qualification.

Host integer RMS primitives pass24 official-coefficient fixtures within one
output code; four attention fixtures preserve masked long rows within one
context output code. Q16 probabilities preserve a uniform2,048-key row that
Q8 would round to zeros. Synthetic arithmetic scales are not task calibration.
6/7/8-bit candidate tile codecs preserve supplied integer codes for embedding
lookup and projection; nine real-weight packing fixtures pass. This proves
packing, not the quality of quantizing weights to those widths.

The new isolated packed_weight_row16 RTL unpacks 16 signed codes from a row into
INT8 lanes with one elastic register. All {sum(r['rows'] for r in rtl['checks']):,} simulated rows pass across
6/7/8-bit configurations, including every representable code, checkpoint-derived
samples, tile padding/boundaries, unused high bits, stalls, reset flushing and
back-to-back transfers. Isolated Vivado synthesis completed for all three widths
on xck26-sfvc784-2LV-c. This is offline FPGA implementation work: it is not
connected to the executor, DDR fetch, dot product or R5 ABI, and is not routed,
timing-qualified or tested on the board. Simulation does not establish the
quality of weight quantization.
Synthesis uses {', '.join(str(r['luts']) for r in rtl_synthesis['configurations'])} LUTs and
{', '.join(str(r['registers']) for r in rtl_synthesis['configurations'])} registers for 6/7/8 bits respectively.

Uniform INT8 weights alone occupy268,098,176 bytes, leaving337,280 bytes in the
current256MiB region; an INT8 KV cache adds7,070,208 bytes. The conditional ledger
also includes norm/scale records, rotary tables, decoder pieces, scratch and
firmware/mailbox/header assumptions. Its totals are:

| Shared embedding/projection width | Estimated total bytes | Margin in256MiB |
|---|---:|---:|
'''
    for option in storage['options']:
        text+=f"| {option['embedding_bits']} bits; other matrices8 | {option['total_bytes']:,} | {option['margin_bytes']:,} |\n"
    text+='''
These are estimates, not allocated executable images. In particular, the7-bit
option's margin is small; INT16 KV, additional padding/storage or a different
scratch schedule can exceed it. The6-bit option has more margin but unmeasured
whole-model accuracy. No bit width has been selected. Existing UINT16 token
transport is incompatible with the model vocabulary; proposed storage is32-bit,
with an embedding-range check. Added tokenizer image IDs262144/262145 lack text
embeddings and must be rejected. All1,240 declared text requests passed input
preflight; none was filtered on that basis.

No deployed image, R5 firmware, module, reserved-memory layout or dashboard was
changed. The new helpers are offline references. DDR fetch/unpacker integration, integer rotary
and gated activation integration, whole-model quantization/calibration, R5
token-piece decoding, typed-call payload validation and compiler/module ABI
still need implementation and qualification. Preserve the calibrated MiniLM
deployment. Reuse existing publication-gate work, but finite-label schemas and
128-token timing admission do not silently authorize this general-call profile.
A terminal record by D is distinct from successful inference and Linux delivery.
All 49 relevant local tests passed. Prior sealed artifacts were hash-verified
unchanged, and the new run/report/source artifacts have a separate seal.
'''
    # Keep prose readable without changing code, labels or sealed old sources.
    for a,b in [('allow256','allow 256'),('generator2048','generator 2048'),('and256','and 256'),('most8','most 8'),('and4','and 4'),('preserves527','preserves 527'),('remaining713','remaining 713'),('of4','of 4'),('All25','All 25'),('and1,241','and 1,241'),('width256','width 256'),('GQA4','GQA 4'),('Gemma1','Gemma 1'),('all18','all 18'),('full262','full 262'),('atol0','atol 0'),('rtol0','rtol 0'),('the512','the 512'),('position8192','position 8192'),('pass24','pass 24'),('uniform2','uniform 2'),('occupy268','occupy 268'),('leaving337','leaving 337'),('current256','current 256'),('adds7','adds 7'),('in256','in 256'),('matrices8','matrices 8'),('the7','the 7'),('The6','The 6'),('is32','is 32'),('IDs262','IDs 262'),('All1,240','All 1,240')]:text=text.replace(a,b)
    out.mkdir(parents=True);report.write_text(text,encoding='utf-8')
    (out/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    before=(training/'HANDOFF.before-progress.md').read_bytes()
    prefix=f'''# Current continuation - expanded general-tool reference complete

## New-chat start here (expanded software evidence and offline Gemma foundations)

Read docs/research/2026-10-18-general-tool-expanded-reference.md and
build/v2/general-tool-expanded-report-v4/comparison.json. User domain remains
GENERAL TOOL/FUNCTION CALLING. No family winner or new hardware qualification.
Corrected encoder training v4 is COMPLETE:2,048 original requests+256 denials,
two epochs, selected {train['best']}, dev selection {chosen['result']['correct']}/20,
separate component-disjoint audit {summary['encoder_training']['audit']['correct']}/72.
No span-target round-trip failures. Full1,240-request BFCL results:
encoder {results['encoder']['summary']['correct']}/1240; frozen official FunctionGemma
{results['functiongemma_official']['summary']['correct']}/1240. Always-Reject {reject}/1240.
This is not matched task training/compute or a human blind test. Full v3 tuned
FunctionGemma evaluation, adequate training and calibration remain pending.

Run roots: build/v2/general-tool-expanded-training-v4/encoder and
build/v2/general-tool-expanded-evaluation-v4/(encoder-full,encoder-parity,
functiongemma-official-full,functiongemma-batch4-parity). Reference retains527
completed single-request records plus713 batch4 results.25 exact saved-output
parity checks passed. One administrative in-flight interruption retained and
reissued; no completed failure retried. Original single-request root is stopped,
not complete. All completed failures remain in the full benchmark denominator.

OFFLINE only: functiongemma_float_ops/streaming_float provide an independent
18-layer float reference; all {len(decoder['checks'])} generated tokens matched stock eager FP32 on
one fixture. Six block fixtures,24 RMS fixtures,4 Q16 attention fixtures and9
packed-code fixtures pass. No whole-model integer accuracy, integrated image or board
qualification is claimed. A separate packed_weight_row16 RTL block passes
{sum(r['rows'] for r in rtl['checks']):,} simulated rows and isolated KR260 synthesis at 6/7/8 bits;
records are under functiongemma-packed-rtl-v2. No routing/timing/executor or
board integration yet. Numerical/codecs/resource records are under functiongemma-float-ops-v1,
functiongemma-decoder-float-v1,functiongemma-integer-ops-v1,functiongemma-storage-v2.
Uniform INT8 weights+KV do not fit the current256MiB region. Conditional7-bit
embedding estimate has666,482 bytes margin;6-bit has21,638,002. Accuracy and actual
layout are unqualified. Token IDs need a new32-bit transport, with text embedding
range checks; tokenizer added image IDs262144/262145 are unsupported. All1,240
declared text inputs pass preflight. Do not load any of these through current ABI.

Preserve all old seals and new build/v2/general-tool-expanded-report-v4/seal.json.
No model/evaluation job is left running. No paid compute, commit/push, automation
or BOARD COMMANDS/CHANGES. Calibrated MiniLM PL/model/R5 remains untouched;
JTAG/hw_server/XSDB/cs_server stay stopped, Linux running, no raw probes/power
cycle/stock restore/module unload/dashboard restart. Keep credentials out of logs.
Next: assess full results; improve adequate task capability/calibration before
choosing a family, then qualify whole-model integer path and both R5-controlled
FPGA ports. General-call payload typing/publication and terminal-by-D integration
remain distinct from inference correctness and from Linux delivery.

---

'''
    for a,b in [('COMPLETE:2','COMPLETE: 2'),('requests+256','requests + 256'),('selection{','selection {'),('audit{','audit {'),('Full1,240','Full 1,240'),('encoder{','encoder {'),('Always-Reject{','Always-Reject {'),('retains527','retains 527'),('plus713','plus 713'),('batch4','batch 4'),('results.25','results. 25'),('all{','all {'),('fixtures,24','fixtures, 24'),('fixtures,4','fixtures, 4'),('and9','and 9'),('current256','current 256'),('Conditional7','Conditional 7'),('has666','has 666'),('margin;6','margin; 6'),('has21','has 21'),('new32','new 32'),('IDs262','IDs 262'),('All1,240','All 1,240')]:prefix=prefix.replace(a,b)
    (out/'handoff-prefix.md').write_text(prefix,encoding='utf-8')
    (out/'HANDOFF.before-prefix.md').write_bytes(before)
    (ROOT/'HANDOFF.md').write_bytes(prefix.encode('utf-8')+before)
    paths=list(training.rglob('*'))+list(evaluations.rglob('*'))+list(out.rglob('*'))+[report,Path(__file__)]
    for folder in ['functiongemma-float-ops-v1','functiongemma-decoder-float-v1','functiongemma-integer-ops-v1','functiongemma-storage-v1','functiongemma-storage-v2','functiongemma-packed-rtl-v1','functiongemma-packed-rtl-v2']:
        paths+=list((ROOT/'build/v2'/folder).rglob('*'))
    paths+=list((ROOT/'src/sysone/v2').glob('functiongemma_*.py'))
    paths+=list((ROOT/'tests').glob('test_functiongemma_*.py'))
    paths += [ROOT/name for name in train['source_sha256']]
    paths += [ROOT/name for value in foundations.values() for name in value['source_sha256']]
    paths += [ROOT/'scripts/v2/kr260/check_packed_weight_row_ooc.tcl']
    paths += [ROOT/'scripts/v2'/name for name in ['evaluate_general_reference_v4.py','evaluate_functiongemma_batch.py','evaluate_functiongemma_batch_resume.py',
        'qualify_functiongemma_float_ops.py','qualify_functiongemma_integer_ops.py','qualify_functiongemma_decoder_float.py','plan_functiongemma_storage.py','preflight_functiongemma_reference.py']]
    files={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in paths if p.is_file()}
    (out/'seal.json').write_text(json.dumps(dict(observed_utc=datetime.now(timezone.utc).isoformat(),files=files,files_count=len(files)),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(report=str(report),full_results={k:v['summary']['correct'] for k,v in results.items()},prior_files_verified=len(prior_files),new_sealed_files=len(files))))


if __name__=='__main__':main()
