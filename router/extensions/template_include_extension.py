import re
from pathlib import Path

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class TemplateIncludeExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(
            TemplateIncludePreprocessor(md), "template_include", 15
        )


class TemplateIncludePreprocessor(Preprocessor):
    RE = re.compile(r"(?<!\\)!template\[(?P<name>[^\]]+)\]")

    def run(self, lines):
        out = []
        for line in lines:
            m = self.RE.search(line)
            if not m:
                out.append(line)
                continue

            name = m.group("name").strip()
            template_file = (Path("wiki/_template") / f"{name}.md").resolve()

            if not template_file.exists():
                out.append(f'<span class="missing">Template {name} not found</span>')
                continue

            try:
                content = template_file.read_text(encoding="utf-8").splitlines()
                out.extend(content)

            except Exception as e:
                out.append(f"Error reading '{name}': {e}")

        return out
