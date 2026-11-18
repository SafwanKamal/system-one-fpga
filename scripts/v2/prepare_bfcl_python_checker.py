"""Stage pinned, unmodified BFCL checker with a local model-registry adapter.

No model/provider handlers are imported. Only Python evaluation is used here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

REV='6ea57973c7a6097fd7c5915698c54c17c5b1b6c8'
FILES=('constants/enums.py','constants/type_mappings.py',
       'eval_checker/ast_eval/ast_checker.py',
       'eval_checker/ast_eval/type_convertor/java_type_converter.py',
       'eval_checker/ast_eval/type_convertor/js_type_converter.py')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    receipts=[]
    for name in FILES:
        url=f'https://raw.githubusercontent.com/ShishirPatil/gorilla/{REV}/berkeley-function-call-leaderboard/bfcl_eval/{name}'
        with urllib.request.urlopen(url,timeout=30) as response:
            content=response.read()
        target=args.out/'bfcl_eval'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(content)
        receipts.append(dict(path=name,url=url,sha256=hashlib.sha256(content).hexdigest(),modified=False))
        for parent in target.parents:
            if parent==args.out:
                break
            (parent/'__init__.py').touch(exist_ok=True)
    registry=args.out/'bfcl_eval/constants/model_config.py'
    registry.write_text('"""Local registry adapter; not the upstream provider registry."""\n'
        'from types import SimpleNamespace\n'
        'MODEL_CONFIG_MAPPING={"sysone/local":SimpleNamespace(underscore_to_dot=False)}\n',encoding='utf-8')
    with urllib.request.urlopen(f'https://raw.githubusercontent.com/ShishirPatil/gorilla/{REV}/LICENSE',timeout=30) as response:
        (args.out/'LICENSE').write_bytes(response.read())
    (args.out/'receipt.json').write_text(json.dumps(dict(revision=REV,files=receipts,
        registry_adapter='local entries only, no name rewriting; no remote model provider imports',
        registry_sha256=hashlib.sha256(registry.read_bytes()).hexdigest(),
        scope='Unmodified upstream checker functions; Python-only local adapter, not a leaderboard submission'),indent=2)+'\n')
    print(args.out)


if __name__=='__main__':
    main()
