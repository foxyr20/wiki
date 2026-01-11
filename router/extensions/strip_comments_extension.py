import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class StripCommentsExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(StripCommentsPreprocessor(md), "strip_comments", 5)


class StripCommentsPreprocessor(Preprocessor):
    RE = re.compile(r"<!--.*?-->", re.DOTALL)

    def run(self, lines):
        text = "\n".join(lines)
        text = self.RE.sub("", text)
        stripped_lines = [line.rstrip() for line in text.split("\n")]
        while stripped_lines and not stripped_lines[0].strip():
            stripped_lines.pop(0)

        while stripped_lines and not stripped_lines[-1].strip():
            stripped_lines.pop()

        return stripped_lines
