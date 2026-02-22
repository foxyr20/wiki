import re
from xml.etree import ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

from template_env import static_url


class ButtonExtension(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(
            ButtonBlockProcessor(md.parser),
            "wiki_button",
            170,
        )


class ButtonBlockProcessor(BlockProcessor):
    START_RE = re.compile(r"^\s*!button\[\s*$")
    END_RE = re.compile(r"^\s*\]\s*$")

    def test(self, parent, block):
        lines = block.splitlines()
        return bool(lines and self.START_RE.match(lines[0]))

    def run(self, parent, blocks):
        block = blocks.pop(0)
        lines = block.splitlines()

        lines = lines[1:]

        data: list[str] = []

        for line in lines:
            if self.END_RE.match(line.strip()):
                break
            if line.strip():
                data.append(line.strip())

        if len(data) < 2:
            return True

        url = data[0]
        name = data[1]
        desc = None
        image = None

        if len(data) >= 3:
            if data[2].lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                image = data[2]
            else:
                desc = data[2]

        if len(data) >= 4:
            image = data[3]

        a = etree.SubElement(parent, "a")
        a.set("class", "wiki-button")
        a.set("href", url)

        if image:
            icon = etree.SubElement(a, "span")
            icon.set("class", "wiki-button-icon")

            img = etree.SubElement(icon, "img")
            img.set("src", static_url(image))
            img.set("alt", "")

        meta = etree.SubElement(a, "span")
        meta.set("class", "wiki-button-meta")

        title = etree.SubElement(meta, "span")
        title.set("class", "wiki-button-title")
        title.text = name

        if desc:
            d = etree.SubElement(meta, "span")
            d.set("class", "wiki-button-desc")
            d.text = desc

        return True
