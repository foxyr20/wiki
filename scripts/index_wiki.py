from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import Constants

WIKI_DIR = Path("wiki")
OUT_DIR = Path("static/search")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = OUT_DIR / "wiki_index.json"
META_FILE = OUT_DIR / "wiki_index.meta.json"


# Regex
WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}", re.U)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)\s*$")
META_KV_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$")

LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^[^\]]+\]\s*:\s*")
FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]]+\]")

HR_RE = re.compile(r"^\s*---+\s*$")
DIRECTIVE_LINE_RE = re.compile(r"^\s*!(\w+)\b")

CONSTANT_RE = re.compile(r"!constant\[([^\]]+)\]")

DIALOG_START_RE = re.compile(r"^\s*!dialog_start\[\s*$")
DIALOG_END_RE = re.compile(r"^\s*!dialog_end\s*$")
DIALOG_PARTICIPANT_RE = re.compile(
    r"""
    ^\s*
    (?P<key>[^:]+)
    :
    \s*
    (?P<side>left|right|center)
    (?P<opts>.*)
    $
    """,
    re.X,
)
DIALOG_SAY_RE = re.compile(r"^\s*([^:]+)\s*:\s*(.+?)\s*$")
DIALOG_AT_RE = re.compile(r"^\s*@([^ ]+)\s*(.*)\s*$")

OPTION_RE = re.compile(
    r"""
    (\w+)
    =
    (?:
        "([^"]+)"
        |
        ([^\s]+)
    )
    """,
    re.X,
)

FOLDER_START_RE = re.compile(r"^\s*!folder\[\s*$")
FOLDER_END_RE = re.compile(r"^\s*]\s*$")

RESTRICTED_START_RE = re.compile(r"^\s*!restricted\[\s*$")
RESTRICTED_END_RE = re.compile(r"^\s*!restricted_end\s*$")

REDACT_INLINE_RE = re.compile(r"!redact\[(.*?)\]")

IMAGE_START_RE = re.compile(r"^\s*!image\[\s*$")
IMAGE_FLOAT_BREAK_RE = re.compile(r"^\s*!image_float_break\s*$")

BUTTON_START_RE = re.compile(r"^\s*!button\[\s*$")
AUTO_BUTTONS_RE = re.compile(r"^\s*!auto_buttons\b")

TEMPLATE_RE = re.compile(r"^\s*!template\[")
CLOSE_BRACKET_RE = re.compile(r"^\s*]\s*$")


# Helpers
def normalize(text: str) -> str:
    return text.lower()


def tokenize(text: str) -> list[str]:
    return sorted(set(WORD_RE.findall(normalize(text))))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_options(s: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v1, v2 in OPTION_RE.findall(s or ""):
        out[k] = v1 or v2
    return out


def strip_links(text: str) -> str:
    return LINK_RE.sub(r"\1", text)


def strip_footnote_refs(text: str) -> str:
    return FOOTNOTE_REF_RE.sub("", text)


def strip_inline_code(text: str) -> str:
    return text.replace("`", "")


def collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# CONSTANT handling
def substitute_constants(text: str) -> str:
    """
    Try to substitute !constant[name] from Constants.
    If not found — remove later.
    """

    def repl(m: re.Match) -> str:
        key = m.group(1)
        if Constants is not None and hasattr(Constants, key):
            val = getattr(Constants, key)
            return str(val) if val is not None else ""
        return ""

    return CONSTANT_RE.sub(repl, text)


def sanitize_text(text: str) -> str:
    """
    Unified text sanitizer for search index.
    """
    text = substitute_constants(text)
    text = strip_links(text)
    text = strip_inline_code(text)
    text = strip_footnote_refs(text)
    return collapse_spaces(text)


# Data model
@dataclass
class Section:
    kind: str
    text: str
    level: int | None = None
    speaker: str | None = None


# Parsing
def read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def remove_html_comments(lines: list[str]) -> list[str]:
    out: list[str] = []
    in_comment = False

    for raw in lines:
        line = raw
        while True:
            if not in_comment:
                start = line.find("<!--")
                if start == -1:
                    out.append(line)
                    break

                prefix = line[:start]
                rest = line[start + 4 :]
                end = rest.find("-->")
                if end == -1:
                    out.append(prefix)
                    in_comment = True
                    break

                line = prefix + rest[end + 3 :]

            else:
                end = line.find("-->")
                if end == -1:
                    break

                line = line[end + 3 :]
                in_comment = False

    return out


def split_meta_header(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    meta: dict[str, str] = {}
    i = 0
    seen_any = False

    while i < len(lines):
        s = lines[i].rstrip("\n")
        if not s.strip():
            if seen_any:
                i += 1
            break

        m = META_KV_RE.match(s.strip())
        if not m:
            break

        seen_any = True
        meta[m.group(1)] = m.group(2).strip()
        i += 1

    return meta, lines[i:]


def index_page(md_path: Path) -> dict:
    rel = md_path.relative_to(WIKI_DIR).with_suffix("")
    raw = read_md(md_path)
    lines = remove_html_comments(raw.splitlines())
    meta, lines = split_meta_header(lines)

    sections: list[Section] = []

    def push_text(txt: str):
        cleaned = sanitize_text(txt)
        if cleaned:
            sections.append(Section(kind="text", text=cleaned))

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if not s or HR_RE.match(s):
            i += 1
            continue

        m_h = HEADING_RE.match(line)
        if m_h:
            txt = sanitize_text(m_h.group(2))
            if txt:
                sections.append(
                    Section(kind="heading", text=txt, level=len(m_h.group(1)))
                )
            i += 1
            continue

        if DIRECTIVE_LINE_RE.match(s):
            i += 1
            continue

        push_text(line)
        i += 1

    flat_text = "\n".join(s.text for s in sections)
    tokens = tokenize(flat_text)

    title = meta.get("Title") or rel.name.replace("_", " ").title()
    authors_raw = meta.get("Author", "").strip()
    authors = (
        [a.strip() for a in authors_raw.split(",") if a.strip()] if authors_raw else []
    )

    return {
        "path": str(rel).replace("\\", "/"),
        "title": title,
        "meta": {
            "author": authors,
            "date": meta.get("Date", ""),
        },
        "text": flat_text,
        "tokens": tokens,
        "sections": [
            {
                "kind": s.kind,
                "text": s.text,
                **({"level": s.level} if s.level is not None else {}),
                **({"speaker": s.speaker} if s.speaker is not None else {}),
            }
            for s in sections
        ],
    }


# Index
def is_template_path(path: Path) -> bool:
    return "_template" in path.parts


def build_index():
    pages: list[dict] = []

    for md in sorted(WIKI_DIR.rglob("*.md")):
        if not is_template_path(md):
            pages.append(index_page(md))

    index = {
        "version": 2,
        "pages": pages,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    raw_json = json.dumps(index, ensure_ascii=False, sort_keys=True)
    digest = sha256_text(raw_json)

    INDEX_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    META_FILE.write_text(
        json.dumps(
            {
                "hash": f"sha256:{digest}",
                "updated": datetime.now(timezone.utc).isoformat(),
                "pages": len(pages),
                "version": index["version"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Indexed {len(pages)} pages")
    print(f"Hash: {digest}")


def is_index_stale() -> bool:
    if not INDEX_FILE.exists():
        return True

    index_mtime = INDEX_FILE.stat().st_mtime
    for md in WIKI_DIR.rglob("*.md"):
        if not is_template_path(md) and md.stat().st_mtime > index_mtime:
            return True

    return False


if __name__ == "__main__":
    build_index()
