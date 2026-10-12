#!/usr/bin/env python3
"""Explicitly copy an authorized source to a new candidate; never edit source."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="获授权后复制候选，并输出修改前字节哈希；不自动润色")
    ap.add_argument("original", type=Path)
    ap.add_argument("candidate", type=Path)
    args = ap.parse_args()
    source = args.original.expanduser().resolve()
    target = args.candidate.expanduser().absolute()
    if not source.is_file():
        ap.error("原稿不存在")
    data = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(data)
    except FileExistsError:
        ap.error("候选路径已存在；另起序号，不覆盖任何已有文件")
    digest = sha256(data).hexdigest()
    print(json.dumps({"original": str(source), "candidate": str(target),
                      "original_sha256": digest, "candidate_sha256": digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
