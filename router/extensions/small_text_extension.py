import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class SmallTextExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(
            SmallTextPreprocessor(),
            "small_text",
            30,
        )


class SmallTextPreprocessor(Preprocessor):
    RE = re.compile(r"^\s*-\#\s*(.*)$")

    def run(self, lines):
        out: list[str] = []

        for line in lines:
            m = self.RE.match(line)
            if not m:
                out.append(line)
                continue

            text = m.group(1)
            out.append(f'<div class="small-text">{text}</div>')

        return out
