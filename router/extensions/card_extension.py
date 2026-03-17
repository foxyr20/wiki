import re
from xml.etree import ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

from .block_utils import (
    find_end_index,
    find_match_in_lines,
    has_matching_line,
    parse_prefix_blocks,
    push_suffix_block,
)


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
        return has_matching_line(block, self.START_RE)

    def run(self, parent, blocks):
        block = blocks.pop(0)
        lines = block.splitlines()

        start_idx, start_match = find_match_in_lines(lines, self.START_RE)
        color = start_match.group("color") if start_match else None

        if start_idx is None:
            return True

        parse_prefix_blocks(self.parser, parent, lines[:start_idx])

        section = etree.SubElement(parent, "section")
        section.set("class", "card")
        if color:
            section.set("style", f"--card-accent:{color};")

        content: list[str] = []
        ended = False

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if self.END_RE.match(line.strip()):
                push_suffix_block(blocks, lines[i + 1 :])
                ended = True
                break

            content.append(line)

        while blocks and not ended:
            blk = blocks.pop(0)
            blk_lines = blk.splitlines()
            end_idx = find_end_index(blk_lines, self.END_RE)

            if end_idx is None:
                if content:
                    content.append("")

                content.extend(blk_lines)
                continue

            if end_idx > 0:
                if content:
                    content.append("")

                content.extend(blk_lines[:end_idx])

            push_suffix_block(blocks, blk_lines[end_idx + 1 :])
            ended = True
            break

        text = "\n".join(content).strip()
        if text:
            self.parser.parseBlocks(section, text.split("\n\n"))  # type: ignore

        return True
