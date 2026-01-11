from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

WIKI_DIR = Path("wiki")
OUT_DIR = Path("static/search")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = OUT_DIR / "wiki_index.json"
META_FILE = OUT_DIR / "wiki_index.meta.json"

WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}", re.U)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)\s*$")
META_KV_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$")

LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
WIKILINK_RE = re.compile(r"\[([^\]]+)\]\((/wiki/[^)]+)\)")

FOOTNOTE_DEF_RE = re.compile(r"^\[\^[^\]]+\]\s*:\s*")
FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]]+\]")

HR_RE = re.compile(r"^\s*---+\s*$")

DIRECTIVE_LINE_RE = re.compile(r"^\s*!(\w+)\b")

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


@dataclass
class Section:
    kind: str
    text: str
    level: int | None = None
    speaker: str | None = None


def read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def remove_html_comments(lines: list[str]) -> list[str]:
    """
    Remove <!-- ... --> including multiline.
    """
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
                    line = prefix
                    in_comment = True
                    out.append(line)
                    break

                suffix = rest[end + 3 :]
                line = prefix + suffix

                continue
            else:
                end = line.find("-->")
                if end == -1:
                    line = ""
                    break

                line = line[end + 3 :]
                in_comment = False

                continue

    return out


def split_meta_header(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """
    Extract meta like:
    Title: ...
    Author: ...
    Date: ...
    ...
    Only from the very top, until first blank line or non "Key: Value".
    """
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
    lines = raw.splitlines()

    lines = remove_html_comments(lines)

    meta, lines = split_meta_header(lines)

    sections: list[Section] = []

    in_dialog = False
    dialog_participants: dict[str, dict[str, str]] = {}
    dialog_key_to_name: dict[str, str] = {}

    in_restricted = False

    in_button = False

    in_folder = False
    folder_paths: list[str] = []

    in_image = False
    image_opts: dict[str, str] = {}

    def push_text(line_text: str):
        t = collapse_spaces(
            strip_footnote_refs(strip_inline_code(strip_links(line_text)))
        )
        if t:
            sections.append(Section(kind="text", text=t))

    def flush_folder():
        nonlocal folder_paths
        if folder_paths:
            joined = "\n".join(folder_paths)
            sections.append(Section(kind="folder", text=joined))
            folder_paths = []

    def flush_image_alt(opts: dict[str, str]):
        alt = (opts.get("alt") or "").strip()
        if alt:
            sections.append(Section(kind="image_alt", text=collapse_spaces(alt)))

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.rstrip("\n")
        s = line.strip()

        if s == "[TOC]":
            i += 1
            continue

        if HR_RE.match(s):
            i += 1
            continue

        if not in_restricted and RESTRICTED_START_RE.match(s):
            in_restricted = True
            i += 1
            continue

        if in_restricted:
            if RESTRICTED_END_RE.match(s):
                in_restricted = False
            i += 1
            continue

        if TEMPLATE_RE.match(s):
            i += 1
            continue

        if AUTO_BUTTONS_RE.match(s):
            i += 1
            continue

        if IMAGE_FLOAT_BREAK_RE.match(s):
            i += 1
            continue

        if not in_button and BUTTON_START_RE.match(s):
            in_button = True
            i += 1
            continue

        if in_button:
            if CLOSE_BRACKET_RE.match(s):
                in_button = False
            i += 1
            continue

        if not in_folder and FOLDER_START_RE.match(s):
            in_folder = True
            folder_paths = []
            i += 1
            continue

        if in_folder:
            if FOLDER_END_RE.match(s):
                in_folder = False
                flush_folder()
                i += 1
                continue

            if s:
                folder_paths.append(s)
            i += 1
            continue

        if not in_image and IMAGE_START_RE.match(s):
            in_image = True
            image_opts = {}
            i += 1
            continue

        if in_image:
            if FOLDER_END_RE.match(s):
                in_image = False
                flush_image_alt(image_opts)
                i += 1
                continue

            if "=" in s:
                image_opts.update(parse_options(s))
            i += 1
            continue

        if not in_dialog and DIALOG_START_RE.match(s):
            in_dialog = True
            dialog_participants = {}
            dialog_key_to_name = {}

            i += 1
            while i < len(lines):
                hs = lines[i].strip()
                if hs == "]":
                    break
                if hs == r"\]":
                    break

                m = DIALOG_PARTICIPANT_RE.match(lines[i].strip())
                if m:
                    key = m.group("key").strip()
                    opts = parse_options(m.group("opts"))
                    name = (opts.get("name") or key).strip()
                    dialog_participants[key] = {
                        "name": name,
                        "side": m.group("side").strip(),
                        "avatar": (opts.get("avatar") or "").strip(),
                    }
                    dialog_key_to_name[key] = name
                i += 1

            i += 1
            continue

        if in_dialog:
            if DIALOG_END_RE.match(s):
                in_dialog = False
                i += 1
                continue

            m_at = DIALOG_AT_RE.match(s)
            if m_at:
                key = m_at.group(1).strip()
                opts = parse_options(m_at.group(2) or "")
                if "name" in opts and opts["name"].strip():
                    dialog_key_to_name[key] = opts["name"].strip()

                i += 1
                continue

            m_say = DIALOG_SAY_RE.match(s)
            if m_say:
                key = m_say.group(1).strip()
                text = m_say.group(2).strip()

                text = REDACT_INLINE_RE.sub("", text).strip()

                speaker = (
                    dialog_key_to_name.get(key)
                    or dialog_participants.get(key, {}).get("name")
                    or key
                )
                cleaned = collapse_spaces(
                    strip_footnote_refs(strip_inline_code(strip_links(text)))
                )
                if cleaned:
                    sections.append(
                        Section(kind="dialog", speaker=speaker, text=cleaned)
                    )
                i += 1
                continue

            i += 1
            continue

        m_h = HEADING_RE.match(line)
        if m_h:
            level = len(m_h.group(1))
            txt = collapse_spaces(
                strip_footnote_refs(strip_inline_code(strip_links(m_h.group(2))))
            )
            if txt:
                sections.append(Section(kind="heading", text=txt, level=level))
            i += 1
            continue

        if FOOTNOTE_DEF_RE.match(s):
            i += 1
            continue

        if "!redact[" in s:
            s2 = REDACT_INLINE_RE.sub("", line)

            if not s2.strip():
                i += 1
                continue
            push_text(s2)
            i += 1
            continue

        m_dir = DIRECTIVE_LINE_RE.match(s)
        if m_dir:
            i += 1
            continue

        if s:
            push_text(line)

        i += 1

    parts: list[str] = []
    for sec in sections:
        if sec.kind == "heading":
            parts.append(sec.text)
        elif sec.kind == "dialog":
            parts.append(f"{sec.speaker}: {sec.text}")
        elif sec.kind == "folder":
            parts.append(sec.text)
        elif sec.kind == "image_alt":
            parts.append(sec.text)
        else:
            parts.append(sec.text)

    flat_text = "\n".join(parts).strip()
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
            "background": meta.get("Background", ""),
            "button_image": meta.get("ButtonImage", ""),
            "button_desc": meta.get("ButtonDesc", ""),
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


def is_template_path(path: Path) -> bool:
    return "_template" in path.parts


def build_index():
    pages: list[dict] = []

    for md in sorted(WIKI_DIR.rglob("*.md")):
        if is_template_path(md):
            continue

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
        if "_template" in md.parts:
            continue
        if md.stat().st_mtime > index_mtime:
            return True

    return False


if __name__ == "__main__":
    build_index()
