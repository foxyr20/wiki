import re
import xml.etree.ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

from template_env import static_url


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
        for line in block.splitlines():
            if line.strip():
                return bool(self.START_RE.match(line.strip()))
        return False

    def run(self, parent, blocks):
        block = blocks.pop(0)
        lines = block.splitlines()

        start = None
        for i, line in enumerate(lines):
            if self.START_RE.match(line.strip()):
                start = i + 1
                break

        if start is None:
            return True

        data = []
        for line in lines[start:]:
            if self.END_RE.match(line.strip()):
                break
            if line.strip():
                data.append(line.strip())

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
        return bool(self.RE.match(block.strip()))

    def run(self, parent, blocks):
        blocks.pop(0)
        div = etree.SubElement(parent, "div")
        div.set("class", "wiki-image-float-break")
        return True
