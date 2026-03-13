#!/usr/bin/env python3

import re
from pathlib import Path

import language_tool_python

BASE = Path(__file__).parent
WIKI_PATH = BASE.parent / "wiki"

REPORT_PATH = BASE / "grammar_report.txt"
DICT_PATH = BASE / "dictionary.txt"

tool_ru = language_tool_python.LanguageTool("ru-RU")
tool_en = language_tool_python.LanguageTool("en-US")

IGNORE_RULES = {
    "DOUBLE_SPACE",
    "UPPERCASE_SENTENCE_START",
    "EN_UNPAIRED_BRACKETS",
    "RU_UNPAIRED_BRACKETS",
    "EN_GB_SIMPLE_REPLACE",
    "EN_GB_SPELLING",
}

project_words: set[str] = set()
project_patterns: list[re.Pattern] = []


if DICT_PATH.exists():
    for raw in DICT_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()

        if not line:
            continue

        if line.startswith("re:"):
            pattern = line[3:].strip()
            project_patterns.append(re.compile(pattern))
        else:
            project_words.add(line.lower())


CODE_BLOCK_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`.*?`")
LINK_RE = re.compile(r"\[(.*?)\]\((.*?)\)")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

MACRO_RE = re.compile(r"!\w+\[(.*?)\]", re.S)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^\)]*\)")
PATH_RE = re.compile(r"\b[\w\-\/]+\.(png|jpg|jpeg|gif|webp|md)\b")

META_RE = re.compile(r"^(Title|Author|Date|Background):.*$", re.M)

LATIN_RE = re.compile(r"[A-Za-z]")


def strip_markdown(text: str) -> str:
    text = CODE_BLOCK_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)

    text = HTML_COMMENT_RE.sub("", text)

    text = IMAGE_RE.sub("", text)

    text = LINK_RE.sub(r"\1", text)

    text = MACRO_RE.sub(r"\1", text)

    text = META_RE.sub("", text)

    text = PATH_RE.sub("", text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def ignore_line(line: str) -> bool:

    s = line.strip()

    if not s:
        return True

    if s.startswith("!"):
        return True

    if s.startswith("[TOC]"):
        return True

    if s.startswith(("Title:", "Author:", "Date:", "Background:")):
        return True

    if "|" in s:
        return True

    return False


def is_project_word(word: str) -> bool:
    w = word.lower()

    if w in project_words:
        return True

    for pattern in project_patterns:
        if pattern.fullmatch(word):
            return True

    return False


def check_file(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    clean = strip_markdown(text)

    issues = []

    for lineno, line in enumerate(clean.splitlines(), 1):
        if ignore_line(line):
            continue

        matches = tool_ru.check(line)

        if LATIN_RE.search(line):
            matches.extend(tool_en.check(line))

        for m in matches:
            if m.rule_id in IGNORE_RULES:
                continue

            if m.offset >= len(line):
                continue

            word = line[m.offset : m.offset + m.error_length]

            if is_project_word(word):
                continue

            column = m.offset + 1
            suggestion = ", ".join(m.replacements[:3]) if m.replacements else ""

            issues.append(
                f"{path}:{lineno}:{column}\n"
                f"word: {word}\n"
                f"message: {m.message}\n"
                f"suggest: {suggestion}\n"
                f"line: {line.strip()}\n\n"
            )

    return issues


def main():
    results: list[str] = []
    try:
        files = sorted(WIKI_PATH.rglob("*.md"))

        total = len(files)

        for i, file in enumerate(files, 1):
            print(f"[{i}/{total}] {file}")

            results.extend(check_file(file))

        REPORT_PATH.write_text("".join(results), encoding="utf-8")

        print(f"\nIssues: {len(results)}")
        print(f"Report: {REPORT_PATH}")

    except KeyboardInterrupt:
        REPORT_PATH.write_text("".join(results), encoding="utf-8")
        print("\nInterrupted by user")
        print(f"Partial report saved: {REPORT_PATH}")
        return


if __name__ == "__main__":
    main()
