"""Run Stage generation over local persona directories."""

import argparse
import random
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument(
        "--style-example-file",
        required=True,
        help="Authorised Aveni consultation excerpt used for Stage generation",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    persona_root = Path(args.persona_root)
    output_root = Path(args.out_root)
    script = Path(__file__).with_name("generate_stage.py")

    persona_dirs = sorted(
        path for path in persona_root.iterdir()
        if path.is_dir() and (path / "customer.json").exists() and (path / "adviser.json").exists()
    )
    if not persona_dirs:
        raise ValueError("No persona directories containing customer.json and adviser.json were found")

    failures = []
    rng = random.Random(args.seed)
    for index, persona_dir in enumerate(persona_dirs, start=1):
        out_dir = output_root / persona_dir.name
        command = [
            sys.executable,
            str(script),
            "--persona-dir", str(persona_dir),
            "--out-dir", str(out_dir),
            "--style-example-file", str(Path(args.style_example_file).resolve()),
        ]
        if args.overwrite:
            command.append("--overwrite")
        if args.max_turns is not None:
            command.extend(["--max-turns", str(args.max_turns)])
        if args.seed is not None:
            command.extend(["--seed", str(rng.randrange(0, 2 ** 32))])
        print("[%d/%d] %s" % (index, len(persona_dirs), persona_dir.name))
        result = subprocess.run(command, cwd=Path(__file__).parent.parent)
        if result.returncode:
            failures.append(persona_dir.name)

    if failures:
        raise RuntimeError("Generation failed for: %s" % ", ".join(failures))


if __name__ == "__main__":
    main()
