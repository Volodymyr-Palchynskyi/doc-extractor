import argparse
import asyncio
import logging
import sys

from app.core.config import settings
from evals.runner import OracleExtractor, build_report, run_split, save
from evals.synth.dataset import SPLITS, load_split


# Ablation baseline: the schema is still enforced, but none of the extraction rules are given.
MINIMAL_INSTRUCTION = "Extract the invoice data from the document."


async def main_async(args: argparse.Namespace) -> int:
    if args.split == "test" and not args.final:
        print(
            "Refusing to run the sealed test split without --final.\n"
            "It is for reporting a finished configuration once, never for iterating. Use --split dev while building.",
            file=sys.stderr,
        )
        return 2

    samples = load_split(args.split)
    if args.limit:
        samples = samples[: args.limit]

    if args.extractor == "oracle":
        extractor = OracleExtractor(samples)
    else:
        from app.services.extraction_service import GeminiExtractor
        extractor = GeminiExtractor(MINIMAL_INSTRUCTION) if args.prompt == "minimal" else GeminiExtractor()

    results = await run_split(extractor, samples)
    name = f"{args.split}_{args.tag or (args.extractor + ("_minimal-prompt" if args.prompt == "minimal" else ""))}"
    title = f"Extraction eval: {args.split} split, extractor `{args.extractor}`" + (f", model `{settings.GEMINI_MODEL}`" if args.extractor == "gemini" else "")
    report = build_report(results, title)
    print(report)
    save(name, report, results, {"split": args.split, "extractor": args.extractor, "model": settings.GEMINI_MODEL})
    if args.extractor == "oracle" and not all(r.score and r.score.exact for r in results):
        print("The oracle must score 100%: the harness and the dataset disagree.", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m evals")
    parser.add_argument("--split", choices=list(SPLITS), default="dev")
    parser.add_argument("--extractor", choices=["gemini", "oracle"], default="gemini")
    parser.add_argument("--limit", type=int, default=0, help="only the first N documents (cheap smoke runs)")
    parser.add_argument("--prompt", choices=["full", "minimal"], default="full", help="minimal = ablation without the extraction rules")
    parser.add_argument("--tag", default="", help="suffix for the report file name")
    parser.add_argument("--final", action="store_true", help="required to run the sealed test split")
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
