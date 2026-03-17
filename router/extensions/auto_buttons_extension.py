import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from markdown import Markdown
from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

from .block_utils import (
    find_match_in_lines,
    has_matching_line,
    parse_prefix_blocks,
    push_suffix_block,
)

RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

META_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+)$")


class AutoButtonsExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {
            "wiki_dir": [Path("wiki"), "Root wiki directory"],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown):
        md.parser.blockprocessors.register(
            AutoButtonsBlockProcessor(
                md.parser,
                Path(self.getConfig("wiki_dir")),
                md,
            ),
            "auto_buttons",
            160,
        )


class AutoButtonsBlockProcessor(BlockProcessor):
    RE = re.compile(r"^\s*!auto_buttons(?:\[(?P<args>[^\]]+)\])?\s*$")

    def __init__(self, parser, wiki_dir: Path, md: Markdown):
        super().__init__(parser)
        self.wiki_dir = wiki_dir.resolve()
        self.md = md

    def test(self, parent, block):
        return has_matching_line(block, self.RE)

    def run(self, parent, blocks):
        block = blocks.pop(0)
        block_lines = block.splitlines()

        cmd_idx, cmd_match = find_match_in_lines(block_lines, self.RE)

        if cmd_idx is None or cmd_match is None:
            return True

        parse_prefix_blocks(self.parser, parent, block_lines[:cmd_idx])

        sort_mode = (cmd_match.group("args") or "abc").strip().lower()

        current_file: Optional[Path] = getattr(self.md, "current_file", None)
        if not current_file:
            push_suffix_block(blocks, block_lines[cmd_idx + 1 :])
            return True

        current_file = Path(current_file).resolve()
        folder = current_file.parent

        items = self._collect(folder, current_file)

        if sort_mode == "time":
            items.sort(key=lambda x: x["date"], reverse=True)
        else:
            items.sort(key=lambda x: x["title"].lower())

        md_blocks: list[str] = []

        for it in items:
            item_lines = [
                "!button[",
                f"    {it['href']}",
                f"    {it['title']}",
            ]

            if it.get("desc"):
                item_lines.append(f"    {it['desc']}")

            if it.get("image"):
                item_lines.append(f"    {it['image']}")

            item_lines.append("]")

            md_blocks.append("\n".join(item_lines))

        push_suffix_block(blocks, block_lines[cmd_idx + 1 :])

        blocks[:0] = md_blocks
        return True

    def _collect(self, folder: Path, current: Path):
        out = []

        for md_file in folder.glob("*.md"):
            if md_file.resolve() == current:
                continue

            meta = self._read_meta(md_file)

            out.append(
                {
                    "title": meta.get("title") or md_file.stem,
                    "href": self._href_from(md_file),
                    "date": self._parse_date(meta.get("date"), md_file.stat().st_mtime),
                    "desc": meta.get("buttondesc"),
                    "image": meta.get("buttonimage"),
                }
            )

        for sub in folder.iterdir():
            index = sub / "index.md"
            if not index.exists():
                continue

            meta = self._read_meta(index)

            out.append(
                {
                    "title": meta.get("title") or sub.name,
                    "href": self._href_from(index),
                    "date": self._parse_date(meta.get("date"), index.stat().st_mtime),
                    "desc": meta.get("buttondesc"),
                    "image": meta.get("buttonimage"),
                }
            )

        return out

    def _href_from(self, md_path: Path) -> str:
        rel = md_path.resolve().relative_to(self.wiki_dir).with_suffix("")
        return "/wiki/" + str(rel).replace("\\", "/")

    def _read_meta(self, md_path: Path) -> dict[str, str]:
        try:
            lines = md_path.read_text(encoding="utf-8").splitlines()

        except FileNotFoundError:
            return {}

        meta: dict[str, str] = {}
        in_meta = True

        for line in lines:
            if not in_meta:
                break

            if not line.strip():
                break

            m = META_LINE_RE.match(line)
            if not m:
                break

            key, value = m.groups()
            meta[key.lower()] = value.strip()

        return meta

    def _parse_date(self, raw: Optional[str], fallback_ts: float) -> datetime:
        if not raw:
            return datetime.fromtimestamp(fallback_ts)

        raw = raw.strip()

        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(raw, fmt)

            except ValueError:
                pass

        parts = raw.split()
        if len(parts) >= 3:
            try:
                return datetime(
                    int(parts[2]),
                    RU_MONTHS[parts[1].lower()],
                    int(parts[0]),
                )

            except Exception:
                pass

        return datetime.fromtimestamp(fallback_ts)
