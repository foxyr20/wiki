import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from markdown import Markdown
from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

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
        return bool(self.RE.match(block.strip()))

    def run(self, parent, blocks):
        block = blocks.pop(0)
        m = self.RE.match(block.strip())
        sort_mode = (m.group("args") or "abc").strip().lower()  # type: ignore

        current_file: Optional[Path] = getattr(self.md, "current_file", None)
        if not current_file:
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
            lines = [
                "!button[",
                f"    {it['href']}",
                f"    {it['title']}",
            ]

            if it.get("desc"):
                lines.append(f"    {it['desc']}")

            if it.get("image"):
                lines.append(f"    {it['image']}")

            lines.append("]")

            md_blocks.append("\n".join(lines))

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
                    "desc": self._join(meta.get("buttondesc")),
                    "image": self._first(meta.get("buttonimage")),
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
                    "desc": self._join(meta.get("buttondesc")),
                    "image": self._first(meta.get("buttonimage")),
                }
            )

        return out

    def _href_from(self, md_path: Path) -> str:
        rel = md_path.resolve().relative_to(self.wiki_dir).with_suffix("")
        return "/wiki/" + str(rel).replace("\\", "/")

    def _read_meta(self, md_path: Path) -> dict:
        try:
            text = md_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}

        head = []
        for line in text.splitlines():
            if not line.strip():
                break
            head.append(line)

        md = Markdown(extensions=["meta"])
        md.convert("\n".join(head))

        return {
            k.lower(): (v[0] if isinstance(v, list) else v)
            for k, v in getattr(md, "Meta", {}).items()
        }

    def _join(self, value):
        if isinstance(value, list):
            return " ".join(v.strip() for v in value if v.strip())
        return value

    def _first(self, value):
        if isinstance(value, list):
            return value[0]
        return value

    def _parse_date(self, raw, fallback_ts):
        if not raw:
            return datetime.fromtimestamp(fallback_ts)

        raw = str(raw).strip()

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
