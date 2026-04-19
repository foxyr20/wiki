import re
from pathlib import Path

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from .strip_comments_extension import strip_html_comments

ATX_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})[ \t]+(.+?)\s*$")
SETEXT_HEADING_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
TEMPLATE_DIR = Path("wiki/_tech/template")


class TemplateIncludeExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(
            TemplateIncludePreprocessor(md), "template_include", 15
        )


class TemplateIncludePreprocessor(Preprocessor):
    RE = re.compile(r"(?<!\\)!template\[(?P<name>[^\]]+)\]")

    def run(self, lines):
        out: list[str] = []
        line_from_template: list[bool] = []

        for line in lines:
            m = self.RE.search(line)
            if not m:
                out.append(line)
                line_from_template.append(False)
                continue

            name = m.group("name").strip()
            template_file = self._resolve_template_path(name)

            if template_file is None:
                out.append(f'<span class="missing">Template {name} not found</span>')
                line_from_template.append(False)
                continue

            try:
                template_text = template_file.read_text(encoding="utf-8")
                raw_content = strip_html_comments(template_text).splitlines()
                for row in raw_content:
                    out.append(row)
                    line_from_template.append(True)

            except Exception as e:
                out.append(f"Error reading '{name}': {e}")
                line_from_template.append(False)

        setattr(
            self.md,
            "wiki_heading_sequence",
            collect_heading_sequence(out, line_from_template),
        )

        return out

    def _resolve_template_path(self, name: str) -> Path | None:
        filename = f"{name}.md"
        candidate = (TEMPLATE_DIR / filename).resolve()
        if candidate.exists():
            return candidate
        return None


def collect_heading_sequence(
    lines: list[str], line_from_template: list[bool]
) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        m_fence = FENCE_RE.match(line)
        if m_fence:
            token = m_fence.group(1)
            marker_char = token[0]
            marker_len = len(token)

            if not in_fence:
                in_fence = True
                fence_char = marker_char
                fence_len = marker_len
            elif marker_char == fence_char and marker_len >= fence_len:
                in_fence = False

            i += 1
            continue

        if in_fence:
            i += 1
            continue

        m_atx = ATX_HEADING_RE.match(line)
        if m_atx:
            heading = normalize_heading_text(m_atx.group(2))
            if heading:
                out.append((heading, line_from_template[i]))

            i += 1
            continue

        if (
            i + 1 < len(lines)
            and line.strip()
            and SETEXT_HEADING_RE.match(lines[i + 1])
        ):
            heading = normalize_heading_text(line)
            if heading:
                out.append((heading, line_from_template[i]))

            i += 2
            continue

        i += 1

    return out


def normalize_heading_text(text: str) -> str:
    text = re.sub(r"\s+#+\s*$", "", text.strip())
    return re.sub(r"\s+", " ", text).strip()
