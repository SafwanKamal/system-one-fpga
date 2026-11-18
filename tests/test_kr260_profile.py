import pytest
from scripts.v2.kr260.summarize_profile import summarize

def test_overlapping_counters_are_not_normalized_to_a_partition():
    counters={'linear_mac_issues':60,'attention_mac_issues':20,'axi_read_beats':10,
              'axi_write_beats':2,'axi_read_bursts':1,'axi_read_service_wait':70,
              'linear_weight_wait':50}
    result=summarize({'clock_hz':1000,'cases':[{'request_clocks':100,'performance_counters':counters}]})
    assert result['axi_read_bytes']==160
    assert result['read_bytes_per_request_second']==1600
    assert result['mac_issue_cycles_per_request_cycle']==.8
    assert result['event_cycles_per_request_cycle']['axi_read_service_wait']==.7
    assert not result['hard_timing_guarantee']

def test_rejects_old_app_without_counters():
    with pytest.raises(ValueError,match='No FPGA counters'):
        summarize({'clock_hz':125000000,'cases':[{'performance_counters':None}]})

def report():
    return {'clock_hz':125000000,'cases':[{'request_clocks':100,
        'performance_counters':{'linear_mac_issues':60,'attention_mac_issues':20,'axi_read_beats':10}}]}

def test_rejects_partial_and_mixed_schema_reports():
    r=report();r['cases'].append({'performance_counters':None})
    with pytest.raises(ValueError,match='Partial'): summarize(r)
    r=report();r['cases'].append({'request_clocks':100,'performance_counters':
        {**r['cases'][0]['performance_counters'],'extra':0}})
    with pytest.raises(ValueError,match='schema'): summarize(r)

@pytest.mark.parametrize('value',[True,-1,1.5,1<<32,'10'])
def test_rejects_invalid_counter_values(value):
    r=report();r['cases'][0]['performance_counters']['axi_read_beats']=value
    with pytest.raises(ValueError,match='counter'): summarize(r)

@pytest.mark.parametrize('value',[True,0,-1,1.5,1<<32,'100'])
def test_rejects_invalid_request_cycles(value):
    r=report();r['cases'][0]['request_clocks']=value
    with pytest.raises(ValueError,match='cycle'): summarize(r)

@pytest.mark.parametrize('value',[True,0,float('nan'),float('inf'),'125000000',1.5])
def test_rejects_invalid_clock(value):
    r=report();r['clock_hz']=value
    with pytest.raises(ValueError,match='clock'): summarize(r)

def test_wrap_evidence_requires_short_measured_host_duration():
    r=report()
    assert not summarize(r)['counter_wrap_excluded_by_host_duration']
    r['cases'][0]['host_round_trip_ms']=1
    assert summarize(r)['counter_wrap_excluded_by_host_duration']
    r['cases'][0]['host_round_trip_ms']=(1<<32)*1000/r['clock_hz']
    with pytest.raises(ValueError,match='wrap'): summarize(r)

@pytest.mark.parametrize('value',[True,-1,float('nan'),float('inf'),'1'])
def test_rejects_invalid_host_duration(value):
    r=report();r['cases'][0]['host_round_trip_ms']=value
    with pytest.raises(ValueError,match='host'): summarize(r)
