from __future__ import annotations

import re
from typing import cast

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

META_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+)$")


class WikiMetaExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.preprocessors.register(
            WikiMetaPreprocessor(md),
            "wiki_meta",
            1000,
        )


class WikiMetaPreprocessor(Preprocessor):
    def run(self, lines: list[str]) -> list[str]:
        meta: dict[str, str] = {}
        new_lines: list[str] = []

        in_meta = True

        for line in lines:
            if in_meta:
                if not line.strip():
                    in_meta = False
                    continue

                m = META_LINE_RE.match(line)
                if m:
                    key, value = m.groups()
                    meta[key.lower()] = value.strip()
                    continue

                in_meta = False

            new_lines.append(line)

        md = cast(Markdown, self.md)
        setattr(md, "wiki_meta", meta)
        return new_lines
