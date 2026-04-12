import re
from typing import Any

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from .block_utils import find_end_index, find_match_in_lines


class RegistryExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(RegistryPreprocessor(md), "registry_block", 24)


class RegistryPreprocessor(Preprocessor):
    START_RE = re.compile(r"^\s*!registry\[\s*$")
    END_RE = re.compile(r"^\s*!registry_end\s*$")
    HEADER_CLOSE_RE = re.compile(r"^(?P<escaped>\\)?]\s*$")

    SECTION_RE = re.compile(r"^(.+?):\s*$")
    VARIANT_RE = re.compile(r"^-\s*([^:]+):\s*(.+)$")
    QUOTE_PAIRS = {
        '"': '"',
        "'": "'",
        "«": "»",
        "„": "“",
        "“": "”",
        "”": "“",
    }

    def run(self, lines):
        out = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if self.START_RE.match(line):
                start_i = i
                header_start = start_i + 1
                body_lines = []
                header_close_rel, header_close_match = find_match_in_lines(
                    lines[header_start:],
                    self.HEADER_CLOSE_RE,
                )

                if header_close_rel is None:
                    # Malformed header. Keep original text and continue safely.
                    out.extend(lines[start_i:])
                    break

                header_close_idx = header_start + header_close_rel
                header_lines = lines[header_start:header_close_idx]
                self_closing = bool(
                    header_close_match and header_close_match.group("escaped")
                )
                i = header_close_idx + 1  # skip ] or \]

                if not self_closing:
                    end_rel = find_end_index(lines[i:], self.END_RE)
                    if end_rel is None:
                        # Header-only registry block (no body, no !registry_end).
                        out.append(self.render_registry(header_lines, []))
                        continue

                    end_idx = i + end_rel
                    body_lines = lines[i:end_idx]
                    i = end_idx + 1

                out.append(
                    self.render_registry(
                        header_lines,
                        body_lines,
                    )
                )
                continue

            out.append(lines[i])
            i += 1

        return out

    def parse_attrs(self, header_lines: list[str]) -> dict[str, str]:
        attrs: dict[str, str] = {}

        for raw in header_lines:
            line = raw.strip()
            if not line or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip().lower()
            if not key:
                continue

            attrs[key] = self._unquote(value.strip())

        return attrs

    def _unquote(self, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            return value

        first = value[0]
        last = value[-1]
        if first == last and first in {'"', "'", "«", "»", "„", "“", "”"}:
            return value[1:-1].strip()

        if first in self.QUOTE_PAIRS and self.QUOTE_PAIRS[first] == last:
            return value[1:-1].strip()

        return value

    def parse_body(self, body_lines: list[str]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for raw in body_lines:
            line = raw.rstrip()
            if not line.strip():
                continue

            m = self.SECTION_RE.match(line)
            if m:
                current = {
                    "title": m.group(1).strip(),
                    "text": [],
                    "variants": [],
                }
                sections.append(current)
                continue

            if current:
                m = self.VARIANT_RE.match(line)
                if m:
                    current["variants"].append(
                        {
                            "key": m.group(1).strip(),
                            "value": m.group(2).strip(),
                        }
                    )
                else:
                    current["text"].append(line)

        return sections

    def render_registry(self, header_lines, body_lines):
        attrs = self.parse_attrs(header_lines)
        sections = self.parse_body(body_lines)

        name = attrs.get("name", "")
        desc = attrs.get("desc", "")

        html = [
            '<div class="registry-entry">',
            '  <div class="registry-head">',
            f'    <div class="registry-name">{name}</div>',
            f'    <div class="registry-desc">{desc}</div>',
            "  </div>",
        ]

        if sections:
            html.append('  <div class="registry-body">')

            for sec in sections:
                html.append(f'    <div class="registry-label">{sec["title"]}</div>')

                if sec["variants"]:
                    html.append('    <div class="registry-variants">')
                    for v in sec["variants"]:
                        html.append(
                            '      <div class="variant">'
                            f'<div class="variant-key">{v["key"]}</div>'
                            f"<div>{v['value']}</div>"
                            "</div>"
                        )
                    html.append("    </div>")
                else:
                    text = "<br>".join(sec["text"])
                    html.append(f'    <div class="registry-text">{text}</div>')

            html.append("  </div>")

        html.append("</div>")

        return "\n".join(html)
