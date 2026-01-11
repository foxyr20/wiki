from xml.etree import ElementTree as etree

from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor


class StrikethroughExtension(Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            StrikethroughProcessor(),
            "strikethrough",
            175,
        )


class StrikethroughProcessor(InlineProcessor):
    RE = r"~~(.*?)~~"

    def __init__(self):
        super().__init__(self.RE)

    def handleMatch(self, m, data):
        el = etree.Element("span")
        el.set("class", "strikethrough")
        el.text = m.group(1)

        return el, m.start(0), m.end(0)
