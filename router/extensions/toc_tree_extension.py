import hashlib
import re
from xml.etree.ElementTree import Element, SubElement

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor

TOC_TOKEN = "TOC_PLACEHOLDER__7d3b3f2a"


class TocTreeExtension(Extension):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.toc_requested: bool = False

    def extendMarkdown(self, md):
        self.toc_requested = False

        md.preprocessors.register(
            TocMarkerPreprocessor(md, self),
            "toc_marker",
            27,
        )
        md.treeprocessors.register(
            TocTreeprocessor(md, self),
            "toc_tree",
            15,
        )

        md.registerExtension(self)


def slugify(text: str) -> str:
    base = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE)
    base = re.sub(r"\s+", "-", base.strip().lower())
    if not base:
        base = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return base


class TocMarkerPreprocessor(Preprocessor):
    RE_TOC = re.compile(r"^\s*\[TOC\]\s*$", re.IGNORECASE)

    def __init__(self, md, ext: TocTreeExtension):
        super().__init__(md)
        self.ext = ext

    def run(self, lines: list[str]) -> list[str]:
        out: list[str] = []

        for line in lines:
            if self.RE_TOC.match(line):
                self.ext.toc_requested = True
                out.append(TOC_TOKEN)
            else:
                out.append(line)

        return out


class TocTreeprocessor(Treeprocessor):
    def __init__(self, md, ext: TocTreeExtension):
        super().__init__(md)
        self.ext = ext

    def run(self, root):
        if not self.ext.toc_requested:
            self._remove_token(root)
            return

        headers: list[tuple[int, str, str]] = []

        for el in root.iter():
            if el.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                text = "".join(el.itertext()).strip()
                if not text:
                    continue

                level = int(el.tag[1])

                anchor = el.get("id")
                if not anchor:
                    anchor = slugify(text)
                    el.set("id", anchor)

                headers.append((level, text, anchor))

        if not headers:
            self._remove_token(root)
            return

        toc_root = Element("div", {"class": "toc"})
        ul_root = SubElement(toc_root, "ul")

        stack: list[tuple[int, Element]] = [(0, ul_root)]

        for level, text, anchor in headers:
            while stack and level <= stack[-1][0]:
                stack.pop()

            parent_ul = stack[-1][1]

            li = SubElement(parent_ul, "li")
            a = SubElement(li, "a", {"href": f"#{anchor}"})
            a.text = text

            child_ul = SubElement(li, "ul")
            stack.append((level, child_ul))

        for li in list(toc_root.iter("li")):
            ul = li.find("ul")
            if ul is not None and len(ul) == 0:
                li.remove(ul)

        if not self._replace_token(root, toc_root):
            root.insert(0, toc_root)

    def _replace_token(self, root, new_el: Element) -> bool:
        for parent in root.iter():
            for i, child in enumerate(list(parent)):
                if self._contains_token(child):
                    parent.remove(child)
                    parent.insert(i, new_el)
                    return True
        return False

    def _remove_token(self, root) -> None:
        for parent in root.iter():
            for child in list(parent):
                if self._contains_token(child):
                    parent.remove(child)

    @staticmethod
    def _contains_token(el) -> bool:
        return TOC_TOKEN in "".join(el.itertext())
