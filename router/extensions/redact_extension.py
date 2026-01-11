import re

from markdown import Markdown
from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor


class RedactExtension(Extension):
    def extendMarkdown(self, md: Markdown):
        md.postprocessors.register(RedactPostprocessor(), "redact_postprocessor", 10)


class RedactPostprocessor(Postprocessor):
    def run(self, text: str) -> str:
        def mask_content(match: re.Match) -> str:
            content = match.group(1)
            return "".join("█" if not c.isspace() else c for c in content)

        pattern = re.compile(r"(?<!\\)!redact\[(.+?)\]")
        text = pattern.sub(mask_content, text)

        return text.replace(r"\!redact", "!redact")
