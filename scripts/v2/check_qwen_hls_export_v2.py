"""Reject stale HLS exports before spending time on a physical decoder build."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/qwen-fpga-decoder-v8'
def normalized(data):
    text=data.decode('utf-8')
    # HLS export adds this simulation-only deadlock hook to its top module.
    # Keep the comparison strict for all executable RTL and port declarations.
    text=re.sub(r'reg find_df_deadlock = 0;\s*// synthesis translate_off\s*`include "[A-Za-z0-9_]+_hls_deadlock_detector\.vh"\s*// synthesis translate_on','',text)
    return '\n'.join(line.rstrip() for line in text.splitlines() if line.strip())
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--solution',type=Path,default=BUILD/'hls-release/solution')
    ap.add_argument('--archive',type=Path,default=BUILD/'qwen_decoder_ip.zip')
    ap.add_argument('--out',type=Path,default=BUILD/'ip-rtl-consistency.json')
    ap.add_argument('--vivado',type=Path,help='Also check the RTL copied into the physical project')
    args=ap.parse_args();solution=args.solution.resolve();ip=solution/'impl/ip'
    sources=sorted((solution/'syn/verilog').glob('*.v'))
    if not sources:raise RuntimeError('No synthesized RTL')
    wrappers=list((solution/'syn/verilog').glob('*integer_dot*_s.v'))
    if len(wrappers)!=1:raise RuntimeError('Matrix dataflow wrapper not identified')
    body=wrappers[0].read_text()
    if 'accumulate_q8' not in body or 'reduce_q8' not in body:raise RuntimeError('Expected staged matrix core absent')
    hashes={};synthesized={};hooks=[]
    with zipfile.ZipFile(args.archive) as archive:
        for source in sources:
            rel='hdl/verilog/'+source.name;data=source.read_bytes();export=ip/rel
            if not export.is_file() or normalized(export.read_bytes())!=normalized(data):raise RuntimeError('Export differs from synthesized RTL: '+source.name)
            exported=export.read_bytes()
            if archive.read(rel)!=exported:raise RuntimeError('Archive differs from exported RTL: '+source.name)
            hashes[rel]=hashlib.sha256(exported).hexdigest();synthesized[rel]=hashlib.sha256(data).hexdigest()
            if exported!=data:hooks.append(source.name)
    result=dict(passed=True,synthesized_RTL_files=len(sources),rtl_sha256=hashes,synthesized_rtl_sha256=synthesized,export_simulation_hooks=hooks,ip_archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),component_xml_sha256=hashlib.sha256((ip/'component.xml').read_bytes()).hexdigest())
    if args.vivado:
        copies=[p for p in args.vivado.rglob('*integer_dot*_s.v') if '/ipshared/' in p.as_posix()]
        if len(copies)!=1:raise RuntimeError('Physical project matrix copy not uniquely identified')
        folder=copies[0].parent
        for name,digest in hashes.items():
            physical=folder/Path(name).name
            if not physical.is_file() or hashlib.sha256(physical.read_bytes()).hexdigest()!=digest:raise RuntimeError('Physical project RTL differs: '+name)
        result['vivado_imported_rtl_verified']=True
        result['vivado_imported_rtl_folder']=folder.relative_to(args.vivado).as_posix()
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,synthesized_RTL_files=len(sources),ip_archive_sha256=result['ip_archive_sha256'])))
if __name__=='__main__':main()
