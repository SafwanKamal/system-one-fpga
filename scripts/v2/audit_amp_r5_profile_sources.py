"""Preserve primary manual pages defining source identity and its collisions."""
from pathlib import Path
import hashlib,json
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-r5-profile-filter-v1'

def main():
    out=BASE/'source-audit-v1';out.mkdir(exist_ok=False)
    source=ROOT/'build/v2/typed200-amp-ownership-v1/ug1085-v2.5.pdf'
    anchor=json.loads((BASE/'prior-validation.json').read_text())
    records={**anchor['preserved_sha256'],**anchor['candidate_sha256']}
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest==records[source.relative_to(ROOT).as_posix()]
    reader=PdfReader(source)
    for page in [63,396,410,411,1091]:
        (out/f'pdf-page-{page}.txt').write_text(reader.pages[page-1].extract_text(),encoding='utf-8')
    collision=(out/'pdf-page-63.txt').read_text(encoding='utf-8')
    assert 'same master ID' in collision and 'SMMU TCU' in collision
    table=(out/'pdf-page-411.txt').read_text(encoding='utf-8')
    assert all(x in table for x in ['RPU0','CCI-400','SMMU TCU'])
    result=dict(passed=True,source_sha256=digest,read_only_source=True,
        rendered_review_required=[63,411],master_identity_bits=[9,0],
        poison_bit=10,shared_mid_zero=['RPU0 AXI ID0','CCI-400','SMMU TCU'],
        user_upper_bits_11_13_semantics_qualified=False,
        source_path_qualified=False,r5_only_from_mid_zero_claim=False,
        primary_sources=[
          'https://docs.amd.com/api/khub/documents/xzMsp_c5sG9J6A3u7NkJYQ/content?Ft-Calling-App=ft',
          'https://docs.amd.com/api/khub/documents/o7UpBPL5dy8b1slLrXVABg/content',
          'https://docs.amd.com/r/en-US/pg201-zynq-ultrascale-plus-processing-system/Port-Descriptions'],
        disposition='No hardware source-authentication deployment until shared MID0 paths and protected endpoint attributes are resolved; separate trusted-Linux diagnostics do not confer isolation')
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS primary source extraction; MID0 source collision confirmed; no target mutation')

if __name__=='__main__':main()
