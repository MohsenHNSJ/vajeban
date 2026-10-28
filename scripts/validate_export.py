#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sanity-check a Gboard dictionary file produced by gboard_export.py.

Usage:
    python scripts/validate_export.py dist/vajeban_gboard_v0.2.0.txt

Exits with status 1 and lists the first problems if the file is not a valid
export, so a broken dictionary is never published.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from gboard_export import HEADER

LANGUAGE_TAG = "fa-IR"
FIELD_COUNT = 4  # shortcut, word, language tag, POS tag (may be empty)
MAX_REPORTED = 10


def validate(text: str, min_records: int) -> tuple[int, list[str]]:
    """Return (record_count, errors) for the contents of an export file."""
    errors: list[str] = []

    if text.startswith("﻿"):
        errors.append("file starts with a UTF-8 BOM")
    if "\r" in text:
        errors.append("file contains carriage returns (CRLF line endings)")
    if not text.endswith("\n"):
        errors.append("file does not end with a newline")

    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    if lines[: len(HEADER)] != HEADER:
        errors.append("the two Gboard header lines are missing or different")

    records = lines[len(HEADER):]
    if len(records) < min_records:
        errors.append(
            f"found {len(records)} record(s), expected at least {min_records}"
        )

    seen: set[str] = set()
    for number, line in enumerate(records, start=len(HEADER) + 1):
        fields = line.rstrip("\r").split("\t")
        if len(fields) != FIELD_COUNT:
            errors.append(
                f"line {number}: expected {FIELD_COUNT} tab-separated fields, "
                f"found {len(fields)}"
            )
            continue
        shortcut, word, tag, _pos = fields
        if not shortcut.strip():
            errors.append(f"line {number}: empty shortcut")
        elif re.search(r"\s", shortcut):
            errors.append(f"line {number}: shortcut contains whitespace")
        if not word.strip():
            errors.append(f"line {number}: empty replacement word")
        if tag != LANGUAGE_TAG:
            errors.append(f"line {number}: language tag is {tag!r}, expected {LANGUAGE_TAG!r}")
        if line in seen:
            errors.append(f"line {number}: duplicate record")
        seen.add(line)

    return len(records), errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Gboard dictionary file produced by gboard_export.py."
    )
    parser.add_argument("dictionary", type=Path, help="Path to the exported .txt file")
    parser.add_argument(
        "--min-records",
        type=int,
        default=1,
        help="Fail if the file has fewer records than this (default: 1)",
    )
    args = parser.parse_args()

    try:
        text = args.dictionary.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Error: cannot read {args.dictionary}: {exc}", file=sys.stderr)
        return 1

    count, errors = validate(text, args.min_records)
    if errors:
        print(f"Invalid dictionary file: {args.dictionary}", file=sys.stderr)
        for message in errors[:MAX_REPORTED]:
            print(f"  - {message}", file=sys.stderr)
        if len(errors) > MAX_REPORTED:
            print(f"  ... and {len(errors) - MAX_REPORTED} more", file=sys.stderr)
        return 1

    print(f"OK: {args.dictionary} has {count:,} valid records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
