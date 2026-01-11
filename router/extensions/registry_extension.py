import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class RegistryExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(RegistryPreprocessor(md), "registry_block", 24)


class RegistryPreprocessor(Preprocessor):
    END_RE = re.compile(r"!registry_end")

    OPTION_RE = re.compile(
        r"""
        (\w+)
        =
        (?:
            "([^"]+)"
            |
            ([^\s]+)
        )
        """,
        re.X,
    )

    SECTION_RE = re.compile(r"^(.+?):\s*$")
    VARIANT_RE = re.compile(r"^-\s*([^:]+):\s*(.+)$")

    def run(self, lines):
        out = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line == "!registry[":
                header_lines = []
                body_lines = []
                self_closing = False

                i += 1
                while i < len(lines):
                    cur = lines[i].strip()

                    if cur == "]":
                        self_closing = False
                        break

                    if cur == r"\]":
                        self_closing = True
                        break

                    header_lines.append(lines[i])
                    i += 1

                i += 1

                if not self_closing:
                    while i < len(lines) and not self.END_RE.match(lines[i]):
                        body_lines.append(lines[i])
                        i += 1

                out.append(
                    self.render_registry(
                        header_lines,
                        body_lines,
                    )
                )
            else:
                out.append(lines[i])

            i += 1

        return out

    def parse_attrs(self, header_lines):
        attrs = {}

        for raw in header_lines:
            for k, v1, v2 in self.OPTION_RE.findall(raw):
                attrs[k] = v1 or v2

        return attrs

    def parse_body(self, body_lines):
        sections = []
        current = None

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
