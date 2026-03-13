import re
from pathlib import Path

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

TEMPLATE_TOC_BEGIN = "__TEMPLATE_INCLUDE_BEGIN__9f2a9b__"
TEMPLATE_TOC_END = "__TEMPLATE_INCLUDE_END__9f2a9b__"
TEMPLATE_HEADING_MARK = "\u2063"


class TemplateIncludeExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(
            TemplateIncludePreprocessor(md), "template_include", 15
        )


class TemplateIncludePreprocessor(Preprocessor):
    RE = re.compile(r"(?<!\\)!template\[(?P<name>[^\]]+)\]")
    HEADING_RE = re.compile(r"^(\s*#{1,6}\s+)(.+)$")

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
                raw_content = template_file.read_text(encoding="utf-8").splitlines()
                content: list[str] = []
                for row in raw_content:
                    m_heading = self.HEADING_RE.match(row)
                    if m_heading:
                        content.append(
                            f"{m_heading.group(1)}{TEMPLATE_HEADING_MARK}{m_heading.group(2)}"
                        )
                    else:
                        content.append(row)
                out.append(TEMPLATE_TOC_BEGIN)
                out.extend(content)
                out.append(TEMPLATE_TOC_END)

            except Exception as e:
                out.append(f"Error reading '{name}': {e}")

        return out
