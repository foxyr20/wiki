import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class RestrictedExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(
            RestrictedPreprocessor(md),
            "restricted_block",
            23,
        )


class RestrictedPreprocessor(Preprocessor):
    END_RE = re.compile(r"!restricted_end")

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

    def run(self, lines):
        out = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line == "!restricted[":
                header_lines = []
                body_lines = []
                self_closing = False

                i += 1
                while i < len(lines):
                    cur = lines[i].strip()

                    if cur == "]":
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
                    self.render_restricted(
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

    def render_restricted(self, header_lines, body_lines):
        attrs = self.parse_attrs(header_lines)

        title = attrs.get("title", "")
        tag = attrs.get("tag", "RESTRICTED")
        state = attrs.get("state", "BLOCKED")

        text = "<br>".join(line.rstrip() for line in body_lines if line.strip())

        html = [
            '<div class="restricted">',
            '  <div class="header">',
            f'    <span class="tag">{tag}</span>',
            f'    <span class="state">{state}</span>',
            "  </div>",
            '  <div class="body">',
        ]

        if title:
            html.append(f'    <p class="title">{title}</p>')

        if text:
            html.append(f'    <p class="text">{text}</p>')

        html.extend(
            [
                "  </div>",
                "</div>",
            ]
        )

        return "\n".join(html)
