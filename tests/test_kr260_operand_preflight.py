"""A stale or incomplete synthesized register inventory must block the new build."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def gate(tmp_path, monkeypatch):
    source = ROOT / 'build/v2/kr260-opt-pipeline-cuts-large'
    if not (source / 'preflight-pipeline-cuts.json').exists():
        pytest.skip('Frozen synthesis evidence is not present')
    folder = tmp_path / 'kr260-opt-operand-capture-large'
    folder.mkdir()
    for path in source.glob('preflight-*'):
        if path.suffix in ('.json', '.rpt', '.txt'):
            shutil.copyfile(path, folder / path.name)
    (folder / 'preflight-operand-capture.json').write_text(json.dumps({
        'probability_input_registered_dsps': 32, 'local_embed_control_ff': 64}))
    (folder / 'preflight-probability-input.txt').write_text(''.join(
        f'probability/lane{i}/product AREG=1 BREG=2 PREG=1\n' for i in range(32)))
    monkeypatch.setattr('sys.argv', ['check_batch_preflight.py'])
    spec = importlib.util.spec_from_file_location('operand_gate', ROOT / 'scripts/v2/kr260/check_batch_preflight.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BUILD = folder
    return module, folder


def test_complete_existing_gates_and_new_stages_admitted(gate):
    module, folder = gate
    module.main()
    summary = json.loads((folder / 'preflight-summary.json').read_text())
    assert summary['all_uram_outputs_registered']
    assert summary['operand_capture']['probability_input_registered_dsps'] == 32
    assert summary['pipeline_cuts']['drain_bank_capture_ff'] >= 256


@pytest.mark.parametrize('change', ['missing_input_stage', 'stale_two_stage_inventory', 'missing_embed_controls'])
def test_incomplete_operand_inference_rejected(gate, change):
    module, folder = gate
    inventory = folder / 'preflight-operand-capture.json'
    data = json.loads(inventory.read_text())
    if change == 'missing_input_stage':
        data['probability_input_registered_dsps'] = 31
    elif change == 'missing_embed_controls':
        data['local_embed_control_ff'] = 0
    else:
        path = folder / 'preflight-probability-input.txt'
        path.write_text(path.read_text().replace('AREG=1 BREG=2', 'AREG=0 BREG=1', 1))
    inventory.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='input capture|local embedding|inventory mismatch'):
        module.main()


@pytest.mark.parametrize('fault', [None, 'missing_bank', 'write_first', 'extra_latency', 'missing_row', 'lutram'])
def test_source_row_bram_contract(gate, fault):
    module, old = gate
    folder = old.with_name('kr260-opt-source-row-bram-large')
    old.rename(folder)
    module.BUILD = folder
    banks = [{'primitive': 'RAMB36E2', 'write_mode_a': 'READ_FIRST',
              'write_mode_b': 'READ_FIRST', 'doa_reg': 0, 'dob_reg': 0}]
    row = {'row_registers': 14, 'linear_lutram_cells': 0}
    if fault == 'missing_bank':
        banks = []
    elif fault == 'write_first':
        banks[0]['write_mode_a'] = 'WRITE_FIRST'
    elif fault == 'extra_latency':
        banks[0]['dob_reg'] = 1
    elif fault == 'missing_row':
        row['row_registers'] = 0
    elif fault == 'lutram':
        row['linear_lutram_cells'] = 1
    (folder / 'preflight-linear-bram.json').write_text(json.dumps(banks))
    (folder / 'preflight-source-row.json').write_text(json.dumps(row))
    if fault:
        with pytest.raises(ValueError, match='LINEAR'):
            module.main()
    else:
        module.main()
        summary = json.loads((folder / 'preflight-summary.json').read_text())
        assert summary['linear_block_bank_primitives'] == 1
        assert summary['operand_capture']['probability_input_registered_dsps'] == 32


@pytest.mark.parametrize('fault', [None, 'stale_32_lanes', 'missing_distance_ff', 'absorbed_distance', 'insufficient_area', 'valid_replica', 'orphan_replica', 'missing_control'])
def test_attention_width_distance_admission(gate, fault):
    module, old = gate
    folder = old.with_name('kr260-opt-attention16-distance-large')
    old.rename(folder)
    module.BUILD = folder
    for name in ['preflight-query-controls.json', 'preflight-accumulator-controls.json']:
        path = folder / name
        path.write_text(json.dumps(json.loads(path.read_text())[:512]))
    controls_path=folder/'preflight-accumulator-controls.json'
    controls=json.loads(controls_path.read_text())
    if fault in ('valid_replica','orphan_replica'):
        controls.append(dict(controls[0],cell=controls[0]['cell']+('_rep' if fault=='valid_replica' else '_unknown_rep')))
    elif fault=='missing_control':
        controls.pop()
    controls_path.write_text(json.dumps(controls))
    path = folder / 'preflight-utilization.rpt'
    path.write_text(path.read_text().replace('90522', '65000'))
    (folder / 'preflight-pipeline-cuts.json').write_text(json.dumps({
        'probability_dsps': 16, 'registered_probability_dsps': 16, 'drain_bank_capture_ff': 256}))
    (folder / 'preflight-operand-capture.json').write_text(json.dumps({
        'probability_input_registered_dsps': 16, 'local_embed_control_ff': 64}))
    (folder / 'preflight-probability-input.txt').write_text(''.join(
        f'probability/lane{i}/product AREG=1 BREG=2 PREG=1\n' for i in range(16)))
    (folder / 'preflight-linear-bram.json').write_text(json.dumps([{
        'primitive': 'RAMB36E2', 'write_mode_a': 'READ_FIRST', 'write_mode_b': 'READ_FIRST', 'doa_reg': 0, 'dob_reg': 0}]))
    (folder / 'preflight-source-row.json').write_text('{"row_registers":15,"linear_lutram_cells":0}')
    mapping = {'query_lanes':16,'external_distance_ff':352,'distance_dsps':16,'distance_dsp_mapping_passed':16}
    if fault == 'stale_32_lanes':
        mapping['query_lanes'] = 32
    elif fault == 'missing_distance_ff':
        mapping['external_distance_ff'] = 0
    elif fault == 'absorbed_distance':
        mapping['distance_dsp_mapping_passed'] = 0
    elif fault == 'insufficient_area':
        path.write_text(path.read_text().replace('65000', '89920'))
    (folder / 'preflight-attention-width-distance.json').write_text(json.dumps(mapping))
    (folder / 'preflight-distance-dsp.txt').write_text(''.join(f'e_product[{i}] AREG=0 PREG=1\n' for i in range(16)))
    if fault and fault != 'valid_replica':
        with pytest.raises(ValueError, match='Attention|LUT relief|control inventory'):
            module.main()
    else:
        module.main()
        result = json.loads((folder / 'preflight-summary.json').read_text())
        assert result['attention_width_distance']['external_distance_ff'] == 352


@pytest.mark.parametrize('fault', [None, 'missing_window', 'missing_dsp', 'unregistered_base', 'extra_latency'])
def test_request_window_embed_admission(gate, fault):
    module, old = gate
    source = ROOT / 'build/v2/kr260-opt-attention16-distance-large'
    if not (source / 'preflight-summary.json').exists():
        pytest.skip('Completed attention16 synthesis evidence unavailable')
    folder = old.with_name('kr260-opt-request-window-embed-large')
    old.rename(folder)
    module.BUILD = folder
    for path in source.glob('preflight-*'):
        if path.suffix in ('.json', '.rpt', '.txt'):
            shutil.copyfile(path, folder / path.name)
    stages = {'request_window_registers': 17, 'embed_address_dsps': 2, 'embed_address_mapping_passed': 2}
    inventory = 'word AREG=1 BREG=1 CREG=1 MREG=0 PREG=1\nposition AREG=1 BREG=1 CREG=1 MREG=0 PREG=1\n'
    if fault == 'missing_window':
        stages['request_window_registers'] = 16
    elif fault == 'missing_dsp':
        stages['embed_address_dsps'] = 1
    elif fault == 'unregistered_base':
        inventory = inventory.replace('CREG=1', 'CREG=0', 1)
    elif fault == 'extra_latency':
        inventory = inventory.replace('MREG=0', 'MREG=1', 1)
    (folder / 'preflight-window-embed.json').write_text(json.dumps(stages))
    (folder / 'preflight-embed-address-dsp.txt').write_text(inventory)
    if fault:
        with pytest.raises(ValueError, match='stage missing|DSP register inventory'):
            module.main()
    else:
        module.main()
        summary = json.loads((folder / 'preflight-summary.json').read_text())
        assert summary['request_window_embed']['embed_address_mapping_passed'] == 2


@pytest.mark.parametrize('fault', [None, 'missing_ff', 'missing_dsp', 'bad_mapping', 'absorbed', 'extra_latency', 'missing_breg'])
def test_context_capture_admission(gate, fault):
    module, old = gate
    source=ROOT/'build/v2/kr260-opt-request-window-embed-large'
    folder=old.with_name('kr260-opt-attention-context-capture-large')
    old.rename(folder); module.BUILD=folder
    for path in source.glob('preflight-*'):
        if path.suffix in ('.json','.rpt','.txt'): shutil.copyfile(path,folder/path.name)
    capture={'fabric_context_ff':92,'context_dsps':4,'mapping_passed':4}
    inventory=''.join(f'context{i} AREG=0 BREG=1 MREG=0 PREG=1\n' for i in range(4))
    if fault=='missing_ff': capture['fabric_context_ff']=91
    elif fault=='missing_dsp': capture['context_dsps']=3
    elif fault=='bad_mapping': capture['mapping_passed']=3
    elif fault=='absorbed': inventory=inventory.replace('AREG=0','AREG=1',1)
    elif fault=='missing_breg': inventory=inventory.replace('BREG=1','BREG=0',1)
    elif fault=='extra_latency': inventory=inventory.replace('MREG=0','MREG=1',1)
    (folder/'preflight-context-capture.json').write_text(json.dumps(capture))
    (folder/'preflight-context-dsp.txt').write_text(inventory)
    if fault:
        with pytest.raises(ValueError,match='context|Context'): module.main()
    else:
        module.main()
        assert json.loads((folder/'preflight-summary.json').read_text())['context_capture']==capture
