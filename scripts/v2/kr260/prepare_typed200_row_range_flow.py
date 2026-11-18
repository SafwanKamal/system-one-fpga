"""Derive new physical helpers without changing any sealed predecessor."""
from create_typed200_row_range_candidate import ROOT,verify
def main():
    verify();folder=ROOT/'scripts/v2/kr260'
    def save(p,s):
        assert not p.exists(),p
        with p.open('w',newline='\n') as f:f.write(s)
    for stem in ('review_typed200_predecode_synthesis.py','review_typed200_predecode_placement.py','audit_typed200_predecode_placement.tcl'):
        s=(folder/stem).read_text().replace('typed200-predecode','typed200-row-range').replace('typed200_predecode','typed200_row_range').replace('(predecode)','(row-range)').replace("'predecode'","'row-range'")
        # Python mapping values use file suffix row_range, not hyphenated experiment tag.
        s=s.replace("'row-range':'row-range'","'row-range':'row_range'")
        if stem.endswith('.tcl'):
            s=s.replace('close_design',r'''set shape_regs [get_cells -quiet -hier -regexp {.*publication_inst/bank_reg\[(5|28)\].*}]
set shape_regs [filter $shape_regs {REF_NAME =~ FD*}]
if {[llength $shape_regs]==0} {error "Missing shape bank registers"}
report_timing -from $shape_regs -delay_type max -max_paths 20 -input_pins -file [file join $out row-range-paths.rpt]
close_design''')
        save(folder/stem.replace('predecode','row_range'),s)
    s=(folder/'build_typed200_predecode_physical.py').read_text()
    s=s.replace('from create_typed200_predecode_candidate import','from create_typed200_row_range_candidate import')
    s=s.replace("default='typed200-predecode-physical-v1'","default='typed200-row-range-physical-v1'")
    s=s.replace("sim=ROOT/'build/v2/typed200-predecode-integration-v1'","sim=ROOT/'build/v2/typed200-row-range-integration-v1'")
    a=s.index("    probe_dir=ROOT/'build/v2/typed200-predecode-ooc-v1'");b=s.index("    build=ROOT/'build/v2'/a.name",a)
    s=s[:a]+'''    import sys
    sys.path.insert(0,str(ROOT/'scripts/v2'))
    from check_typed200_row_range_functional import verify as functional_verify
    functional_verify()
    for tag in ('typed200-row-range-arithmetic-v2','typed200-row-range-endpoint-formal-v1'):
        d=ROOT/'build/v2'/tag;p=json.loads((d/'receipt.json').read_text());assert p['passed']
        for n,h in p['source_sha256'].items():assert sha(ROOT/n)==h,n
        for n,h in p['artifact_sha256'].items():assert sha(d/n)==h,n
    probe_dir=ROOT/'build/v2/typed200-row-range-ooc-v1'
    probe=json.loads((probe_dir/'receipt.json').read_text());assert probe['passed']
    for n,h in probe['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in probe['artifact_sha256'].items():assert sha(probe_dir/n)==h,n
    assert probe['overall_gain_ns']>0 and probe['shape_gain_ns']>0,'No matched overall and shape gain'
'''+s[b:]
    s=s.replace("'clamp_probe_sha256':sha(probe_dir/'receipt.json')", "'row_range_probe_sha256':sha(probe_dir/'receipt.json'),'functional_record_sha256':sha(ROOT/'docs/research/2026-10-16-typed200-row-range-functional.json')")
    save(folder/'build_typed200_row_range_physical.py',s)
    print('PASS isolated row-range physical helpers prepared')
if __name__=='__main__':main()
