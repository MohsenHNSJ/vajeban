#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert a CSV dictionary (word, parsi, UPOS) into a Gboard personal dictionary.

Usage:
    python csv_to_gboard.py input.csv -o gboard_fa_IR.txt

Assumptions:
- CSV columns are named: word, parsi, UPOS (case-insensitive).
- Multiple source words may be separated by commas, semicolons, or slashes.
  Set --word-separator if your file uses a different convention.
- The script conservatively generates shorter prefixes only when enabled with
  --expand-prefixes. Prefixes that already occur as source words are skipped.
  This is a heuristic; it cannot reliably determine whether every prefix has
  an independent meaning.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Iterable

HEADER = [
    "# Gboard Dictionary version:2",
    "# Gboard Dictionary format:shortcut\tword\tlanguage_tag\tpos_tag",
]

# Common delimiters between multiple words. Do not split on whitespace:
# whitespace may be part of a multi-word expression.
DEFAULT_WORD_SEPARATOR = r"[,;؛/|]+"


def normalize_spaces(text: str) -> str:
    """Replace ordinary spaces inside a shortcut with Persian half-spaces."""
    text = text.strip()
    # U+200C is the Persian zero-width non-joiner (half-space).
    return re.sub(r"[ \t\r\n]+", "\u200c", text)


def split_words(value: str, separator_pattern: str) -> list[str]:
    """Split a word field when it contains multiple delimiter-separated words."""
    return [
        part.strip()
        for part in re.split(separator_pattern, value or "")
        if part.strip()
    ]


def read_rows(input_path: Path, encoding: str) -> list[dict[str, str]]:
    """Read CSV rows and map column names case-insensitively."""
    with input_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")
        field_map = {name.strip().lower(): name for name in reader.fieldnames if name}
        required = ("word", "parsi", "upos")
        missing = [name for name in required if name not in field_map]
        if missing:
            raise ValueError(
                "Missing required column(s): "
                + ", ".join(missing)
                + f". Found columns: {', '.join(reader.fieldnames)}"
            )
        result = []
        for row in reader:
            result.append(
                {
                    "word": (row.get(field_map["word"]) or "").strip(),
                    "parsi": (row.get(field_map["parsi"]) or "").strip(),
                    "upos": (row.get(field_map["upos"]) or "").strip(),
                }
            )
        return result


def convert(
    rows: Iterable[dict[str, str]],
    separator_pattern: str,
    expand_prefixes: bool,
    min_prefix_length: int,
) -> list[tuple[str, str, str]]:
    """
    Return unique (shortcut, replacement, POS) records.

    Prefix expansion uses character prefixes and is intentionally heuristic.
    A prefix is skipped if it appears as a full source word anywhere in the CSV.
    """
    rows = list(rows)
    source_words: set[str] = set()
    parsed_rows: list[tuple[list[str], str, str]] = []

    for row in rows:
        words = split_words(row["word"], separator_pattern)
        parsed_rows.append((words, row["parsi"], row["upos"]))
        source_words.update(normalize_spaces(w) for w in words)

    output: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(shortcut: str, replacement: str, pos: str) -> None:
        shortcut = normalize_spaces(shortcut)
        replacement = replacement.strip()
        if not shortcut or not replacement:
            return
        # Gboard shortcut must not contain ordinary whitespace.
        shortcut = re.sub(r"\s+", "\u200c", shortcut)
        record = (shortcut, replacement, pos.strip())
        if record not in seen:
            seen.add(record)
            output.append(record)

    for words, replacement, pos in parsed_rows:
        if not replacement:
            continue
        # Use the first comma-separated Persian equivalent if the source has
        # a list of alternatives, as in "هوازیستی، هوازی".
        replacement = re.split(r"[،;；]", replacement, maxsplit=1)[0].strip()
        for word in words:
            shortcut = normalize_spaces(word)
            if not shortcut:
                continue
            if expand_prefixes:
                # Generate prefixes from longest to shortest, then the full word.
                # Skip very short prefixes and prefixes that are existing words.
                compact = shortcut.replace("\u200c", "")
                prefixes = []
                for end in range(min_prefix_length, len(compact)):
                    prefix = compact[:end]
                    if prefix not in source_words:
                        prefixes.append(prefix)
                for prefix in prefixes:
                    add(prefix, replacement, pos)
            add(shortcut, replacement, pos)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert CSV columns word, parsi, UPOS to a Gboard dictionary text file."
    )
    parser.add_argument("input_csv", type=Path, help="Path to source CSV file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("gboard_fa_IR.txt"),
        help="Output text file (default: gboard_fa_IR.txt)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Input CSV encoding (default: utf-8-sig)",
    )
    parser.add_argument(
        "--word-separator",
        default=DEFAULT_WORD_SEPARATOR,
        help=f"Regex for delimiters between multiple words (default: {DEFAULT_WORD_SEPARATOR!r})",
    )
    parser.add_argument(
        "--expand-prefixes",
        action="store_true",
        help="Add shorter prefixes heuristically; may create ambiguous shortcuts",
    )
    parser.add_argument(
        "--min-prefix-length",
        type=int,
        default=2,
        help="Minimum number of characters in generated prefixes (default: 2)",
    )
    args = parser.parse_args()

    if args.min_prefix_length < 1:
        parser.error("--min-prefix-length must be at least 1")
    if not args.input_csv.is_file():
        parser.error(f"Input file does not exist: {args.input_csv}")

    try:
        rows = read_rows(args.input_csv, args.encoding)
        records = convert(
            rows,
            args.word_separator,
            args.expand_prefixes,
            args.min_prefix_length,
        )
        with args.output.open("w", encoding="utf-8", newline="") as f:
            f.write("\n".join(HEADER) + "\n")
            for shortcut, replacement, pos in records:
                f.write(f"{shortcut}\t{replacement}\tfa-IR\t{pos}\n")
        print(
            f"Processed {len(rows):,} CSV rows; wrote {len(records):,} Gboard records."
        )
        print(f"Output: {args.output.resolve()}")
        return 0
    except (OSError, UnicodeError, csv.Error, ValueError, re.error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
