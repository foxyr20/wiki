import re
from xml.etree import ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

from template_env import static_url

from .block_utils import (
    find_end_index,
    find_match_in_lines,
    has_matching_line,
    parse_prefix_blocks,
    push_suffix_block,
)


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
        return has_matching_line(block, self.START_RE)

    def run(self, parent, blocks):
        block = blocks.pop(0)
        lines = block.splitlines()

        start_idx, _ = find_match_in_lines(lines, self.START_RE)

        if start_idx is None:
            return True

        parse_prefix_blocks(self.parser, parent, lines[:start_idx])

        data: list[str] = []
        ended = False

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if self.END_RE.match(line.strip()):
                push_suffix_block(blocks, lines[i + 1 :])
                ended = True
                break

            if line.strip():
                data.append(line.strip())

        while blocks and not ended:
            blk = blocks.pop(0)
            blk_lines = blk.splitlines()
            end_idx = find_end_index(blk_lines, self.END_RE)

            if end_idx is None:
                for raw in blk_lines:
                    if raw.strip():
                        data.append(raw.strip())

                continue

            for raw in blk_lines[:end_idx]:
                if raw.strip():
                    data.append(raw.strip())

            push_suffix_block(blocks, blk_lines[end_idx + 1 :])
            ended = True
            break

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
