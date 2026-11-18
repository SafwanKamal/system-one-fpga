"""Bundle a frozen evaluation and runtime, optionally including its KR260 model."""
import argparse
import hashlib
from pathlib import Path
import tarfile

from sysone_v2_client import ROOT, load_files
from sysone.v2.encoder_client import LocalEncoder
from sysone.v2.host_heads import Heads
from sysone.v2 import eval_suite
from sysone.v2 import ddr_image
from sysone.v2.encoder_client import RequestLayout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "build/v2/eval/bert-mini-matched.json")
    parser.add_argument("--out", type=Path, default=ROOT / "build/v2/kr260-eval.tar.gz")
    parser.add_argument("--image", default="bert-mini-slots4-kr260")
    parser.add_argument("--include-model", action="store_true",
                        help="include image, manifest, decision rule and tokenizer; extraction does not load DDR")
    args = parser.parse_args()
    image, manifest, _, decision = load_files(args.image)
    model = manifest.get("model_name") or args.image.removesuffix("-kr260")
    header = ddr_image.verify_image(image)
    digest = hashlib.sha256(image).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError("Image SHA256 differs from manifest")
    if (header["base"] != 0x60000000 or header["tile_in"] != 16 or
            header["tile_out"] != 32 or header["hidden"] > 384 or
            header["head_dim"] > 64 or header["max_tokens"] > 128):
        raise ValueError("Image does not fit the deployed KR260 encoder")
    layout = RequestLayout.for_image(header, len(image))
    if layout.result + layout.max_tokens * layout.hidden > 0x64000000:
        raise ValueError("Image and request buffers exceed reserved DDR")
    enc = LocalEncoder(image)
    heads = Heads(manifest, enc.machine, decision)
    checked = eval_suite.load(args.suite, digest,
        hashlib.sha256((ROOT / "export/v2/chain" / model / "tokenizer.json").read_bytes()).hexdigest(),
        heads.labels)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    files = [ROOT / "src/sysone/__init__.py", *sorted((ROOT / "src/sysone/v2").glob("*.py")),
             ROOT / "scripts/v2/sysone_v2_client.py", ROOT / "data/v2/PROVENANCE.md"]
    if args.include_model:
        folder = ROOT / "export/v2/image" / args.image
        files += [folder / f"{args.image}.img", folder / "manifest.json",
                  folder / "program.txt", ROOT / "export/v2/chain" / model / "tokenizer.json"]
        if (folder / "decision.json").exists():
            files.append(folder / "decision.json")
        elif decision is not None:
            files.append(ROOT / "export/v2/image" / model / "decision.json")
    with tarfile.open(args.out, "w:gz") as bundle:
        for path in files:
            bundle.add(path, arcname=path.relative_to(ROOT).as_posix())
        bundle.add(args.suite, arcname=f"build/v2/eval/{args.suite.name}")
    print(f"Prepared {args.out} ({args.out.stat().st_size:,} bytes); {len(checked['cases'])} cases")
    print(f"suite_sha256={checked['suite_sha256']}")


if __name__ == "__main__":
    main()
