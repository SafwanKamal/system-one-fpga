"""Find complete USER-field pages in the already preserved AMD primary manual."""
from pathlib import Path
import hashlib
import json
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-linux-tag-probe-v1'


def main():
    out=BASE/'sideband-audit-v1';out.mkdir(exist_ok=False)
    source=ROOT/'build/v2/typed200-amp-ownership-v1/ug1085-v2.5.pdf'
    prior=json.loads((BASE/'prior-validation.json').read_text())
    records={**prior['preserved_sha256'],**prior['candidate_sha256']}
    with source.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    assert digest==records[source.relative_to(ROOT).as_posix()]
    reader=PdfReader(source);hits=[]
    for i,page in enumerate(reader.pages):
        text=page.extract_text() or ''
        if 'axuser' in text.lower() or 'axi_user' in text.lower():
            (out/f'pdf-page-{i+1}.txt').write_text(text,encoding='utf-8')
            hits.append(i+1);print('USER page '+str(i+1),flush=True)
    (out/'receipt.json').write_text(json.dumps(dict(passed=True,source_sha256=digest,
        source=source.relative_to(ROOT).as_posix(),pdf_pages=len(reader.pages),user_pages=hits,
        read_only_source=True,field_interpretation_qualified=False),indent=2)+'\n')
    print('PASS complete USER-page extraction; inspect table rendering before interpretation',flush=True)


if __name__=='__main__':main()
