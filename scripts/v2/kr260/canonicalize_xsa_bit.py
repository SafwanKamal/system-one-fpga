"""Adopt XSA bit headers only when design, device and FPGA payload are identical."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

def parse(data):
    prefix=b'\x00\x09'+b'\x0f\xf0'*4+b'\x00\x00\x01'
    if not data.startswith(prefix):raise ValueError('Unsupported bit header')
    pos=len(prefix);fields={}
    for tag in b'abcd':
        if pos+3>len(data) or data[pos]!=tag:raise ValueError('Missing bit header field')
        length=int.from_bytes(data[pos+1:pos+3],'big');pos+=3
        if not length or pos+length>len(data):raise ValueError('Truncated bit header field')
        fields[chr(tag)]=data[pos:pos+length];pos+=length
    if pos+5>len(data) or data[pos]!=ord('e'):raise ValueError('Missing FPGA payload')
    length=int.from_bytes(data[pos+1:pos+5],'big');pos+=5
    if not length or pos+length!=len(data):raise ValueError('FPGA payload length mismatch')
    if not re.fullmatch(rb'\d{4}/\d{2}/\d{2}\x00',fields['c']) or not re.fullmatch(rb'\d{2}:\d{2}:\d{2}\x00',fields['d']):
        raise ValueError('Unsupported date/time bit header')
    return fields,data[pos:]

def verify_same_payload(original,embedded):
    a,payload_a=parse(original);b,payload_b=parse(embedded)
    if a['a']!=b['a'] or a['b']!=b['b'] or payload_a!=payload_b:
        raise ValueError('XSA changes design, device or FPGA payload; cannot canonicalize')
    return {'fpga_payload_sha256':hashlib.sha256(payload_a).hexdigest(),
            'original_sha256':hashlib.sha256(original).hexdigest(),
            'canonical_sha256':hashlib.sha256(embedded).hexdigest(),
            'original_time':a['d'].rstrip(b'\0').decode(),'canonical_time':b['d'].rstrip(b'\0').decode()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bit',type=Path,required=True)
    ap.add_argument('--xsa',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args();original=args.bit.read_bytes()
    with zipfile.ZipFile(args.xsa) as z:
        names=[n for n in z.namelist() if n.endswith('.bit')]
        if len(names)!=1:raise ValueError('Exactly one embedded bitstream required')
        embedded=z.read(names[0])
    result=verify_same_payload(original,embedded)
    if original!=embedded:
        backup=args.bit.with_name(args.bit.stem+'.pre-xsa'+args.bit.suffix)
        if backup.exists():raise ValueError('Original export backup already exists; inspect it')
        backup.write_bytes(original);args.bit.write_bytes(embedded)
        result['backup']=str(backup)
    result['changed']=original!=embedded
    args.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
