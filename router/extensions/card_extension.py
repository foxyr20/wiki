import re
from xml.etree import ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension


class CardExtension(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(
            CardBlockProcessor(md.parser),
            "card_block",
            175,
        )


class CardBlockProcessor(BlockProcessor):
    START_RE = re.compile(r"^\s*!card(?:\[(?P<color>[^\]]+)\])?\s*$")
    END_RE = re.compile(r"^\s*!card_end\s*$")

    def test(self, parent, block):
        for line in block.splitlines():
            if line.strip():
                return bool(self.START_RE.match(line.strip()))

        return False

    def run(self, parent, blocks):
        block = blocks.pop(0)
        lines = block.splitlines()

        start = None
        color = None

        for i, line in enumerate(lines):
            m = self.START_RE.match(line.strip())
            if m:
                start = i + 1
                color = m.group("color")
                break

        if start is None:
            return True

        section = etree.SubElement(parent, "section")
        section.set("class", "card")
        if color:
            section.set("style", f"--card-accent:{color};")

        content = []

        for line in lines[start:]:
            if self.END_RE.match(line.strip()):
                break

            content.append(line)

        while blocks:
            blk = blocks.pop(0)
            if self.END_RE.match(blk.strip()):
                break

            content.append("")
            content.extend(blk.splitlines())

        text = "\n".join(content).strip()
        if text:
            self.parser.parseBlocks(section, text.split("\n\n"))  # type: ignore

        return True
