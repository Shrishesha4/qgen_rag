#!/usr/bin/env python
import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--cache-dir", default=str(Path("./models").resolve()))
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN", ""))
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.token:
        os.environ["HUGGINGFACE_HUB_TOKEN"] = args.token
        os.environ["HF_TOKEN"] = args.token

    print(f"Downloading model: {args.model}")
    print(f"Cache directory: {cache_dir}")

    local_path = snapshot_download(
        repo_id=args.model,
        local_dir=str(cache_dir / args.model.replace('/', '__')),
        local_dir_use_symlinks=False,
        token=args.token or None,
        resume_download=True,
    )

    print(f"Model ready at: {local_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)
