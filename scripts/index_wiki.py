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
INDEXER_FILE = Path(__file__).resolve()


# Regex
WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}", re.U)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)\s*$")
META_KV_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$")
TOC_RE = re.compile(r"^\s*\[TOC\]\s*$", re.IGNORECASE)

LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^[^\]]+\]\s*:\s*")
FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]]+\]")
COLOR_TAG_RE = re.compile(r"\[/?color(?:=[^\]]+)?\]", re.IGNORECASE)

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

REGISTRY_START_RE = re.compile(r"^\s*!registry\[\s*$")
REGISTRY_END_RE = re.compile(r"^\s*!registry_end\s*$")

REDACT_INLINE_RE = re.compile(r"(?<!\\)!redact\[(.+?)\]")

IMAGE_START_RE = re.compile(r"^\s*!image\[\s*$")
IMAGE_FLOAT_BREAK_RE = re.compile(r"^\s*!image_float_break\s*$")

BUTTON_START_RE = re.compile(r"^\s*!button\[\s*$")
AUTO_BUTTONS_RE = re.compile(r"^\s*!auto_buttons\b")
HIERARCHY_START_RE = re.compile(r"^\s*!hierarchy\s*$")
HIERARCHY_END_RE = re.compile(r"^\s*!hierarchy_end\s*$")
HIERARCHY_EDGE_RE = re.compile(r"^\s*(?P<src>.+?)\s*-->\s*(?P<dst>.+?)\s*$")
HIERARCHY_COMMENT_RE = re.compile(r"^\s*(#|//)")
HIERARCHY_NODE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
HIERARCHY_NODE_DECL_RE = re.compile(
    r'^(?P<id>[A-Za-z_][A-Za-z0-9_-]*)\s*\[\s*"(?P<label>(?:\\.|[^"\\])*)"\s*\]\s*$'
)

TEMPLATE_RE = re.compile(r"^\s*!template\[")
CLOSE_BRACKET_RE = re.compile(r"^\s*]\s*$")
ESCAPED_CLOSE_BRACKET_RE = re.compile(r"^\s*\\]\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
TABLE_ALIGN_RE = re.compile(r"^\s*\|?[\s:\-]+\|[\s:\-|]*$")

META_KEYS = {
    "title",
    "author",
    "date",
    "background",
    "buttonimage",
    "buttondesc",
}


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
    text = COLOR_TAG_RE.sub("", text)
    text = REDACT_INLINE_RE.sub("", text)
    text = text.replace(r"\!redact", "!redact")
    text = strip_links(text)
    text = strip_inline_code(text)
    text = strip_footnote_refs(text)
    return collapse_spaces(text)


def split_hierarchy_fields(value: str) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    escaped = False

    for ch in value:
        if escaped:
            current.append(ch)
            escaped = False
            continue

        if ch == "\\":
            escaped = True
            continue

        if ch == "|":
            out.append("".join(current))
            current = []
            continue

        current.append(ch)

    if escaped:
        current.append("\\")

    out.append("".join(current))
    return out


def unescape_hierarchy_value(value: str) -> str:
    return (
        value.replace(r"\\", "\\")
        .replace(r"\"", '"')
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
    )


def hierarchy_token_parts(token: str) -> tuple[str | None, str | None]:
    token = token.strip()
    if not token:
        return None, None

    declared = HIERARCHY_NODE_DECL_RE.match(token)
    if declared:
        node_id = declared.group("id")
        fields = split_hierarchy_fields(unescape_hierarchy_value(declared.group("label")))
        title = fields[0].strip() if fields else node_id
        subtitle = fields[1].strip() if len(fields) > 1 else ""
        text = collapse_spaces(" ".join(part for part in (title, subtitle) if part))
        return node_id, text or node_id

    if HIERARCHY_NODE_ID_RE.fullmatch(token):
        return token, None

    return None, None


def extract_hierarchy_texts(block_lines: list[str]) -> list[str]:
    labels: dict[str, str] = {}
    ordered: list[str] = []
    seen: set[str] = set()

    for raw in block_lines:
        line = raw.strip()
        if not line or HIERARCHY_COMMENT_RE.match(line):
            continue

        edge_match = HIERARCHY_EDGE_RE.match(line)
        tokens = [line]
        if edge_match:
            tokens = [edge_match.group("src"), edge_match.group("dst")]

        for token in tokens:
            node_id, text = hierarchy_token_parts(token)
            if node_id and text:
                labels[node_id] = text

    for raw in block_lines:
        line = raw.strip()
        if not line or HIERARCHY_COMMENT_RE.match(line):
            continue

        edge_match = HIERARCHY_EDGE_RE.match(line)
        tokens = [line]
        if edge_match:
            tokens = [edge_match.group("src"), edge_match.group("dst")]

        for token in tokens:
            node_id, text = hierarchy_token_parts(token)
            resolved = text
            if node_id and not resolved:
                resolved = labels.get(node_id)

            resolved = collapse_spaces(resolved or "")
            if resolved and resolved not in seen:
                seen.add(resolved)
                ordered.append(resolved)

    return ordered


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

    def push_text(
        txt: str,
        *,
        kind: str = "text",
        level: int | None = None,
        speaker: str | None = None,
    ) -> None:
        cleaned = sanitize_text(txt)
        if cleaned:
            sections.append(
                Section(
                    kind=kind,
                    text=cleaned,
                    level=level,
                    speaker=speaker,
                )
            )

    in_dialog = False
    dialog_speakers: dict[str, str] = {}
    in_restricted = False
    in_fenced_code = False

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            in_fenced_code = not in_fenced_code
            i += 1
            continue

        if in_fenced_code:
            i += 1
            continue

        if not s or HR_RE.match(s):
            i += 1
            continue

        if TOC_RE.match(s):
            i += 1
            continue

        m_meta = META_KV_RE.match(s)
        if m_meta and m_meta.group(1).lower() in META_KEYS:
            i += 1
            continue

        if in_restricted:
            if RESTRICTED_END_RE.match(s):
                in_restricted = False
            i += 1
            continue

        if DIALOG_START_RE.match(s):
            in_dialog = True
            dialog_speakers.clear()
            i += 1
            continue

        if in_dialog:
            if DIALOG_END_RE.match(s):
                in_dialog = False
                i += 1
                continue

            m_participant = DIALOG_PARTICIPANT_RE.match(line)
            if m_participant:
                key = m_participant.group("key").strip()
                opts = parse_options(m_participant.group("opts") or "")
                name = opts.get("name")
                if name:
                    dialog_speakers[key] = name
                i += 1
                continue

            m_say = DIALOG_SAY_RE.match(line)
            if m_say:
                key = m_say.group(1).strip()
                speaker = dialog_speakers.get(key, key)
                push_text(m_say.group(2), kind="dialog", speaker=speaker)
                i += 1
                continue

            m_at = DIALOG_AT_RE.match(line)
            if m_at:
                push_text(m_at.group(2), kind="dialog", speaker=m_at.group(1))
                i += 1
                continue

            i += 1
            continue

        if RESTRICTED_START_RE.match(s):
            i += 1
            while i < len(lines):
                cur = lines[i].strip()
                if CLOSE_BRACKET_RE.match(cur) or ESCAPED_CLOSE_BRACKET_RE.match(cur):
                    break
                i += 1
            i += 1
            in_restricted = True
            continue

        if REGISTRY_START_RE.match(s):
            reg_start_i = i
            header_lines: list[str] = []
            self_closing = False
            header_closed = False
            i += 1
            while i < len(lines):
                cur = lines[i].strip()
                if ESCAPED_CLOSE_BRACKET_RE.match(cur):
                    header_closed = True
                    self_closing = True
                    break
                if CLOSE_BRACKET_RE.match(cur):
                    header_closed = True
                    break
                header_lines.append(lines[i])
                i += 1

            if not header_closed:
                # malformed header, do not consume following blocks
                i = reg_start_i + 1
                continue

            attrs = parse_options(" ".join(header_lines))
            header_text = " ".join(
                part for part in (attrs.get("name", ""), attrs.get("desc", "")) if part
            )
            push_text(header_text)

            i += 1
            if not self_closing:
                end_idx = i
                while end_idx < len(lines) and not REGISTRY_END_RE.match(
                    lines[end_idx].strip()
                ):
                    end_idx += 1

                if end_idx >= len(lines):
                    # malformed block, parse body as regular text without consuming tail
                    continue

                while i < end_idx:
                    body = lines[i].strip()
                    if body:
                        if body.startswith("-"):
                            bullet = body[1:].strip()
                            if ":" in bullet:
                                key, value = bullet.split(":", 1)
                                if key.strip() and value.strip():
                                    push_text(value.strip())
                                else:
                                    push_text(bullet)
                            else:
                                push_text(bullet)
                        elif body.endswith(":"):
                            push_text(body[:-1])
                        else:
                            push_text(body)
                    i += 1

                i = end_idx + 1
            continue

        if (
            IMAGE_START_RE.match(s)
            or BUTTON_START_RE.match(s)
            or FOLDER_START_RE.match(s)
        ):
            i += 1
            while i < len(lines):
                cur = lines[i].strip()
                if CLOSE_BRACKET_RE.match(cur) or ESCAPED_CLOSE_BRACKET_RE.match(cur):
                    break
                i += 1
            i += 1
            continue

        if (
            TEMPLATE_RE.match(s)
            or AUTO_BUTTONS_RE.match(s)
            or IMAGE_FLOAT_BREAK_RE.match(s)
        ):
            i += 1
            continue

        if HIERARCHY_START_RE.match(s):
            hierarchy_lines: list[str] = []
            i += 1

            while i < len(lines) and not HIERARCHY_END_RE.match(lines[i].strip()):
                hierarchy_lines.append(lines[i])
                i += 1

            for text in extract_hierarchy_texts(hierarchy_lines):
                push_text(text, kind="hierarchy")

            if i < len(lines) and HIERARCHY_END_RE.match(lines[i].strip()):
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

        if TABLE_ROW_RE.match(s):
            if TABLE_ALIGN_RE.match(s):
                i += 1
                continue

            cells: list[str] = []
            for raw_cell in s.strip("|").split("|"):
                cell = raw_cell.strip()
                if not cell:
                    continue
                if cell in {"]", r"\]"}:
                    continue
                if DIRECTIVE_LINE_RE.match(cell):
                    continue
                if cell.startswith("!") and cell.endswith("["):
                    continue

                opts = (
                    parse_options(cell)
                    if "=" in cell and "[" not in cell and "]" not in cell
                    else {}
                )
                if opts:
                    values = [
                        value
                        for value in opts.values()
                        if value and not value.lower().startswith("images/")
                    ]
                    if not values:
                        continue
                    cell = " ".join(values)

                if cell.lower().startswith("images/"):
                    continue

                cells.append(cell)

            push_text(" ".join(cells))
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
    parts = set(path.parts)
    if "_tech" in parts:
        return True
    return False


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
    if INDEXER_FILE.stat().st_mtime > index_mtime:
        return True

    for md in WIKI_DIR.rglob("*.md"):
        if not is_template_path(md) and md.stat().st_mtime > index_mtime:
            return True

    return False


if __name__ == "__main__":
    build_index()
