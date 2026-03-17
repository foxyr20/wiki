import re
import xml.etree.ElementTree as etree

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


class ImageExtension(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(
            ImageBlockProcessor(md.parser),
            "wiki_image",
            150,
        )

        md.parser.blockprocessors.register(
            ImageFloatBreakProcessor(md.parser),
            "wiki_image_float_break",
            149,
        )


class ImageBlockProcessor(BlockProcessor):
    START_RE = re.compile(r"^\s*!image\[\s*$")
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

        if not data:
            return True

        url = data[0]
        args = self._parse_args(data[1:])

        wrapper = etree.SubElement(parent, "div")
        wrapper.set("class", self._build_class(args))

        if "width" in args:
            wrapper.set("style", f"--img-width:{self._normalize_px(args['width'])};")

        img = etree.SubElement(wrapper, "img")
        img.set("src", static_url(url))
        img.set("alt", args.get("alt", ""))

        if args.get("lazy") == "true":
            img.set("loading", "lazy")

        return True

    def _parse_args(self, lines):
        out = {}
        for line in lines:
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip().lower()] = v.strip()

        return out

    def _build_class(self, args):
        cls = ["wiki-image"]
        if "align" in args:
            cls.append(f"align-{args['align']}")

        return " ".join(cls)

    def _normalize_px(self, value):
        return f"{value}px" if value.isdigit() else value


class ImageFloatBreakProcessor(BlockProcessor):
    RE = re.compile(r"^\s*!image_float_break\s*$")

    def test(self, parent, block):
        return has_matching_line(block, self.RE)

    def run(self, parent, blocks):
        block = blocks.pop(0)
        lines = block.splitlines()

        idx, _ = find_match_in_lines(lines, self.RE)

        if idx is None:
            return True

        parse_prefix_blocks(self.parser, parent, lines[:idx])

        div = etree.SubElement(parent, "div")
        div.set("class", "wiki-image-float-break")

        push_suffix_block(blocks, lines[idx + 1 :])

        return True
