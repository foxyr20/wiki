from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as etree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from .link_dictionary import (
    AutoLinkDictionary,
    AutoLinkEntry,
    is_word_char,
    load_autolinks,
    norm_term,
)

SKIP_TAGS = {"a", "code", "pre", "script", "style"}


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]

    return tag


class AutoLinkExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {
            "autolinks_path": [
                Path("wiki/_tech/autolinks.md"),
                "Path to auto-link dictionary",
            ],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown):
        autolinks_path = Path(self.getConfig("autolinks_path"))
        md.treeprocessors.register(
            AutoLinkTreeprocessor(md, autolinks_path),
            "autolink",
            12,
        )


class AutoLinkTreeprocessor(Treeprocessor):
    def __init__(self, md: Markdown, autolinks_path: Path):
        super().__init__(md)
        self.autolinks_path = autolinks_path
        self.dictionary = AutoLinkDictionary(
            by_term={},
            pattern=None,
            first_chars=frozenset(),
            min_term_len=0,
        )

    def run(self, root: etree.Element):
        self.dictionary = load_autolinks(self.autolinks_path)
        if self.dictionary.pattern is None:
            return root

        self._autolink_recursive(root)
        return root

    def _autolink_recursive(self, node: etree.Element):
        tag = _local_tag(node.tag)
        if tag in SKIP_TAGS:
            return

        self._replace_node_text(node)

        i = 0
        while i < len(node):
            child = node[i]
            self._autolink_recursive(child)
            inserted = self._replace_child_tail(node, child, i)
            i += inserted + 1

    def _replace_node_text(self, node: etree.Element):
        fragments = self._split_fragments(node.text or "")
        if not fragments:
            return

        node.text = ""
        insert_pos = 0
        prev_anchor: etree.Element | None = None

        for kind, payload, entry in fragments:
            if kind == "text":
                if prev_anchor is None:
                    node.text = (node.text or "") + payload

                else:
                    prev_anchor.tail = (prev_anchor.tail or "") + payload

                continue

            link = etree.Element("a")
            link.set("href", entry.href)  # type: ignore
            link.set("data-wiki-autolink", "1")
            link.text = payload
            node.insert(insert_pos, link)
            insert_pos += 1
            prev_anchor = link

    def _replace_child_tail(
        self,
        parent: etree.Element,
        child: etree.Element,
        child_idx: int,
    ) -> int:
        fragments = self._split_fragments(child.tail or "")
        if not fragments:
            return 0

        child.tail = ""
        insert_pos = child_idx + 1
        inserted = 0
        prev_node: etree.Element = child

        for kind, payload, entry in fragments:
            if kind == "text":
                prev_node.tail = (prev_node.tail or "") + payload
                continue

            link = etree.Element("a")
            link.set("href", entry.href)  # type: ignore
            link.set("data-wiki-autolink", "1")
            link.text = payload
            parent.insert(insert_pos + inserted, link)
            inserted += 1
            prev_node = link

        return inserted

    def _split_fragments(
        self, text: str
    ) -> list[tuple[str, str, AutoLinkEntry | None]] | None:
        pattern = self.dictionary.pattern
        if not text or pattern is None:
            return None

        if self.dictionary.min_term_len and len(text) < self.dictionary.min_term_len:
            return None

        lowered = text.casefold()
        if self.dictionary.first_chars and not any(
            char in self.dictionary.first_chars for char in lowered
        ):
            return None

        result: list[tuple[str, str, AutoLinkEntry | None]] = []
        last = 0
        has_links = False

        for match in pattern.finditer(text):
            start, end = match.span()
            if not self._has_word_boundaries(text, start, end):
                continue

            key = norm_term(match.group(0))
            entry = self.dictionary.by_term.get(key)
            if entry is None:
                continue

            if start > last:
                result.append(("text", text[last:start], None))

            result.append(("link", text[start:end], entry))
            last = end
            has_links = True

        if not has_links:
            return None

        if last < len(text):
            result.append(("text", text[last:], None))

        return result

    def _has_word_boundaries(self, text: str, start: int, end: int) -> bool:
        if start > 0 and is_word_char(text[start - 1]):
            return False

        if end < len(text) and is_word_char(text[end]):
            return False

        return True
