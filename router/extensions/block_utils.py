from __future__ import annotations

from re import Match, Pattern
from typing import Sequence


def has_matching_line(block: str, pattern: Pattern[str]) -> bool:
    return any(pattern.match(line.strip()) for line in block.splitlines())


def find_match_in_lines(
    lines: Sequence[str], pattern: Pattern[str]
) -> tuple[int | None, Match[str] | None]:
    for i, line in enumerate(lines):
        m = pattern.match(line.strip())
        if m:
            return i, m

    return None, None


def find_end_index(lines: Sequence[str], pattern: Pattern[str]) -> int | None:
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            return i

    return None


def push_suffix_block(blocks, lines: Sequence[str]) -> None:
    tail = "\n".join(lines).strip("\n")
    if tail.strip():
        blocks.insert(0, tail)


def parse_prefix_blocks(parser, parent, lines: Sequence[str]) -> None:
    prefix = "\n".join(lines).strip("\n")
    if prefix.strip():
        parser.parseBlocks(parent, prefix.split("\n\n"))  # type: ignore
