from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as etree

from .block_utils import find_end_index, find_match_in_lines

log = logging.getLogger(__name__)

WHITESPACE_RE = re.compile(r"\s+")
HEADER_CLOSE_RE = re.compile(r"^(?P<escaped>\\)?]\s*$")
SIZE_RE = re.compile(r"^\s*(\d{1,4})(?:px)?\s*$", re.IGNORECASE)

AUTOLINK_START_RE = re.compile(r"^\s*!autolink\[\s*$")

PREVIEW_START_RE = re.compile(r"^\s*!link_preview\[\s*$")
PREVIEW_END_RE = re.compile(r"^\s*!link_preview_end\s*$")


@dataclass(frozen=True)
class AutoLinkEntry:
    term: str
    href: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class AutoLinkDictionary:
    by_term: dict[str, AutoLinkEntry]
    pattern: re.Pattern[str] | None
    first_chars: frozenset[str]
    min_term_len: int


@dataclass(frozen=True)
class PreviewEntry:
    title: str
    image: str | None
    image_width: int | None
    image_height: int | None
    synopsis: str

    @property
    def has_content(self) -> bool:
        return bool(self.image or self.synopsis)


@dataclass(frozen=True)
class PreviewDictionary:
    by_href: dict[str, PreviewEntry]
    by_term: dict[str, PreviewEntry]


@dataclass
class CachedAutoLinks:
    mtime: float | None
    data: AutoLinkDictionary


@dataclass
class CachedPreviews:
    mtime: float | None
    data: PreviewDictionary


_AUTOLINK_CACHE: dict[Path, CachedAutoLinks] = {}
_PREVIEW_CACHE: dict[Path, CachedPreviews] = {}


def norm_spaces(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def norm_term(value: str) -> str:
    return norm_spaces(value).casefold()


def is_word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) < 2:
        return value

    quote_pairs = {
        '"': '"',
        "'": "'",
        "«": "»",
        "„": "“",
        "“": "”",
        "”": "“",
    }
    first, last = value[0], value[-1]
    if first == last and first in {'"', "'", "«", "»", "„", "“", "”"}:
        return value[1:-1].strip()

    if first in quote_pairs and quote_pairs[first] == last:
        return value[1:-1].strip()

    return value


def parse_px_size(value: str | None) -> int | None:
    if value is None:
        return None

    m = SIZE_RE.match(value)
    if not m:
        return None

    parsed = int(m.group(1))
    if parsed <= 0:
        return None

    return min(parsed, 1024)


def href_keys(href: str) -> set[str]:
    raw = href.strip()
    if not raw:
        return set()

    out: set[str] = set()

    def add(value: str) -> None:
        value = value.strip()
        if not value:
            return
        out.add(value.casefold())
        if len(value) > 1 and value.endswith("/"):
            out.add(value[:-1].casefold())

    add(raw)

    split = urlsplit(raw)
    base = split._replace(query="", fragment="").geturl()
    if base and base != raw:
        add(base)

    if not split.scheme and not split.netloc:
        no_hash = raw.split("#", 1)[0]
        no_query = raw.split("?", 1)[0]
        add(no_hash)
        add(no_query)
        add(no_query.split("#", 1)[0])

    return out


def visible_anchor_text(anchor: etree.Element) -> str:
    parts: list[str] = []
    if anchor.text:
        parts.append(anchor.text)

    for child in list(anchor):
        cls = child.get("class", "")
        if "wiki-link-preview-card" in cls:
            if child.tail:
                parts.append(child.tail)
            continue

        parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)

    return norm_spaces("".join(parts))


def parse_kv_header(
    lines: list[str],
    start_idx: int,
    source: Path,
) -> tuple[dict[str, str], int, bool]:
    attrs: dict[str, str] = {}
    close_idx, _ = find_match_in_lines(lines[start_idx:], HEADER_CLOSE_RE)
    if close_idx is None:
        log.warning("Entry has no closing ']' in %s (line %s)", source, len(lines) + 1)
        return attrs, len(lines), False

    end_idx = start_idx + close_idx
    for raw_line in lines[start_idx:end_idx]:
        raw = raw_line.strip()
        if raw and "=" in raw:
            key, value = raw.split("=", 1)
            attrs[key.strip().lower()] = unquote(value.strip())

    return attrs, end_idx + 1, True


def parse_autolinks(path: Path) -> AutoLinkDictionary:
    if not path.exists():
        log.warning("Auto-link dictionary not found: %s", path)
        return AutoLinkDictionary(
            by_term={},
            pattern=None,
            first_chars=frozenset(),
            min_term_len=0,
        )

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        log.warning("Failed to read auto-link dictionary %s: %s", path, exc)
        return AutoLinkDictionary(
            by_term={},
            pattern=None,
            first_chars=frozenset(),
            min_term_len=0,
        )

    by_term: dict[str, AutoLinkEntry] = {}
    # Store pattern variants normalized (lower/casefold) to keep matching mode uniform.
    term_variants: set[str] = set()

    i = 0
    while i < len(lines):
        if not AUTOLINK_START_RE.match(lines[i]):
            i += 1
            continue

        attrs, i, header_closed = parse_kv_header(lines, i + 1, path)
        if not header_closed:
            break

        term_raw = attrs.get("term", "")
        href = attrs.get("href", "").strip()
        term = norm_term(term_raw)

        if not term or not href:
            log.warning(
                "Skipping auto-link entry with missing term/href in %s (term=%r href=%r)",
                path,
                term_raw,
                href,
            )
            continue

        aliases_raw = attrs.get("aliases", "")
        aliases_norm: list[str] = []
        if aliases_raw:
            for alias in aliases_raw.split("|"):
                normalized = norm_term(alias)
                if normalized:
                    aliases_norm.append(normalized)

        entry = AutoLinkEntry(
            term=term,
            href=href,
            aliases=tuple(aliases_norm),
        )

        local_seen: set[str] = set()
        for candidate in (entry.term, *entry.aliases):
            if not candidate or candidate in local_seen:
                continue
            local_seen.add(candidate)

            if candidate in by_term:
                log.warning(
                    "Duplicate auto-link term ignored (%r) in %s: first entry wins",
                    candidate,
                    path,
                )
                continue

            by_term[candidate] = entry
            term_variants.add(candidate)

    if not term_variants:
        return AutoLinkDictionary(
            by_term=by_term,
            pattern=None,
            first_chars=frozenset(),
            min_term_len=0,
        )

    sorted_variants = sorted(term_variants, key=lambda item: (-len(item), item))
    pattern = re.compile(
        "|".join(re.escape(item) for item in sorted_variants),
        re.IGNORECASE,
    )
    first_chars = frozenset(item[0] for item in sorted_variants if item)
    min_term_len = min(len(item) for item in sorted_variants)
    return AutoLinkDictionary(
        by_term=by_term,
        pattern=pattern,
        first_chars=first_chars,
        min_term_len=min_term_len,
    )


def parse_preview_terms(attrs: dict[str, str]) -> list[str]:
    out: list[str] = []

    direct = norm_term(attrs.get("term", ""))
    if direct:
        out.append(direct)

    terms_raw = attrs.get("terms", "")
    if terms_raw:
        for term in terms_raw.split("|"):
            normalized = norm_term(term)
            if normalized:
                out.append(normalized)

    return out


def parse_previews(path: Path) -> PreviewDictionary:
    if not path.exists():
        log.warning("Link preview dictionary not found: %s", path)
        return PreviewDictionary(by_href={}, by_term={})

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        log.warning("Failed to read link preview dictionary %s: %s", path, exc)
        return PreviewDictionary(by_href={}, by_term={})

    by_href: dict[str, PreviewEntry] = {}
    by_term: dict[str, PreviewEntry] = {}
    ambiguous_href_keys: set[str] = set()

    i = 0
    while i < len(lines):
        if not PREVIEW_START_RE.match(lines[i]):
            i += 1
            continue

        attrs, i, header_closed = parse_kv_header(lines, i + 1, path)
        if not header_closed:
            break

        end_rel = find_end_index(lines[i:], PREVIEW_END_RE)
        if end_rel is None:
            log.warning(
                "Link preview entry has no !link_preview_end in %s (line %s)",
                path,
                i + 1,
            )
            break

        end_idx = i + end_rel
        body_lines = lines[i:end_idx]
        i = end_idx + 1

        href = attrs.get("href", "").strip()
        terms = parse_preview_terms(attrs)
        title = norm_spaces(attrs.get("title", ""))

        image = attrs.get("image")
        if image is not None:
            image = image.strip() or None

        image_width = parse_px_size(attrs.get("image_width") or attrs.get("width"))
        image_height = parse_px_size(attrs.get("image_height") or attrs.get("height"))

        synopsis = norm_spaces(
            " ".join(line.strip() for line in body_lines if line.strip())
        )
        preview = PreviewEntry(
            title=title,
            image=image,
            image_width=image_width,
            image_height=image_height,
            synopsis=synopsis,
        )

        if not preview.has_content:
            log.warning(
                "Skipping link preview with empty content in %s (href=%r title=%r)",
                path,
                href,
                title,
            )
            continue

        if not href and not terms:
            log.warning(
                "Skipping link preview without href/term in %s (title=%r)",
                path,
                title,
            )
            continue

        if href:
            for key in href_keys(href):
                if key in ambiguous_href_keys:
                    continue
                if key in by_href:
                    by_href.pop(key, None)
                    ambiguous_href_keys.add(key)
                    log.warning(
                        "Ambiguous link preview href ignored for fallback (%r) in %s",
                        key,
                        path,
                    )
                    continue
                by_href[key] = preview

        local_seen: set[str] = set()
        for term in terms:
            if not term or term in local_seen:
                continue
            local_seen.add(term)
            if term in by_term:
                log.warning(
                    "Duplicate link preview term ignored (%r) in %s: first entry wins",
                    term,
                    path,
                )
                continue
            by_term[term] = preview

    return PreviewDictionary(by_href=by_href, by_term=by_term)


def get_mtime(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def load_autolinks(path: Path) -> AutoLinkDictionary:
    resolved = path.resolve()
    mtime = get_mtime(resolved)
    cached = _AUTOLINK_CACHE.get(resolved)
    if cached and cached.mtime == mtime:
        return cached.data

    data = parse_autolinks(resolved)
    _AUTOLINK_CACHE[resolved] = CachedAutoLinks(mtime=mtime, data=data)
    return data


def load_previews(path: Path) -> PreviewDictionary:
    resolved = path.resolve()
    mtime = get_mtime(resolved)
    cached = _PREVIEW_CACHE.get(resolved)
    if cached and cached.mtime == mtime:
        return cached.data

    data = parse_previews(resolved)
    _PREVIEW_CACHE[resolved] = CachedPreviews(mtime=mtime, data=data)
    return data
