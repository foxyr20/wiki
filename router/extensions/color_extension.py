from xml.etree import ElementTree as etree

from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor


class ColorExtension(Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            ColorInlineProcessor(),
            "color_inline",
            175,
        )


class ColorInlineProcessor(InlineProcessor):
    RE = r"\[color=(?P<color>[^\]]+)\](?P<text>.*?)\[/color\]"

    def __init__(self):
        super().__init__(self.RE)

    def handleMatch(self, m, data):
        color = m.group("color").strip()
        text = m.group("text")

        el = etree.Element("span")
        el.set("style", f"color: {color};")
        el.text = text

        return el, m.start(0), m.end(0)
