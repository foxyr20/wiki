from xml.etree import ElementTree as ET

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor


class FootnoteExtension(Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(
            WikiFootnoteTreeprocessor(md),
            "wiki_footnotes",
            5,
        )


class WikiFootnoteTreeprocessor(Treeprocessor):
    def run(self, root: ET.Element):
        footnotes = root.find(".//div[@class='footnote']")
        if footnotes is None:
            return root

        footnotes.attrib["class"] = "wiki-footnotes"

        ol = footnotes.find("ol")
        if ol is None:
            return root

        for li in ol.findall("li"):
            li.attrib["class"] = "wiki-footnote"

            for a in list(li.findall(".//a")):
                href = a.attrib.get("href", "")
                if href.startswith("#fnref"):
                    parent = li.find(".//p")
                    if parent is not None:
                        parent.remove(a)

        return root
