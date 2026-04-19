import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_html_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


class StripCommentsExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(StripCommentsPreprocessor(md), "strip_comments", 25)


class StripCommentsPreprocessor(Preprocessor):
    def run(self, lines):
        text = "\n".join(lines)
        text = strip_html_comments(text)
        stripped_lines = [line.rstrip() for line in text.split("\n")]
        while stripped_lines and not stripped_lines[0].strip():
            stripped_lines.pop(0)

        while stripped_lines and not stripped_lines[-1].strip():
            stripped_lines.pop()

        return stripped_lines
