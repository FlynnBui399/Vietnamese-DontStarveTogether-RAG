"""Run incremental sync, complete rebuild, embeddings, and atomic activation in order."""

from __future__ import annotations

import argparse
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--skip-sync", action="store_true")
    return parser.parse_args()


def _run(module: str, *arguments: str) -> None:
    subprocess.run([sys.executable, "-m", module, *arguments], check=True)


def main() -> int:
    """Stop at the first failed stage; activation is always the final mutation."""
    args = parse_args()
    if not args.skip_sync:
        _run("scripts.sync_wiki", "--sync-type", "incremental")
    _run("scripts.build_corpus", "--version", args.version)
    _run("scripts.embed_corpus", "--corpus-version", args.version)
    _run("scripts.activate_corpus", "--version", args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
