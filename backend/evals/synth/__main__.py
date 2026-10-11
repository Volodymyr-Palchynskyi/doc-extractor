import argparse

from evals.synth.dataset import SPLITS, build_split


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m evals.synth", description="Regenerate the synthetic datasets")
    parser.add_argument("--split", choices=[*SPLITS, "all"], default="all")
    args = parser.parse_args()
    for split in SPLITS if args.split == "all" else [args.split]:
        print(f"{split}: wrote {build_split(split)} documents")


if __name__ == "__main__":
    main()
