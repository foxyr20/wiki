import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from template_env import static_url


class DialogExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(
            DialogPreprocessor(md),
            "dialog_block",
            25,
        )


class DialogPreprocessor(Preprocessor):
    END_RE = re.compile(r"!dialog_end")

    PARTICIPANT_RE = re.compile(
        r"""
        ^\s*
        (?P<key>[^:]+)
        :
        \s*
        (?P<side>left|right|center)
        (?P<opts>.*)
        $
        """,
        re.X,
    )

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

    LINE_RE = re.compile(r"^\s*([^:]+):\s*(.+)$")
    UPDATE_RE = re.compile(r"^\s*@(\w+)\s+(.*)$")

    def run(self, lines):
        out = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line == "!dialog_start[":
                header_lines = []
                body_lines = []

                i += 1
                while i < len(lines):
                    if lines[i].strip() == "]":
                        break
                    header_lines.append(lines[i])
                    i += 1

                i += 1

                while i < len(lines) and not self.END_RE.match(lines[i]):
                    body_lines.append(lines[i])
                    i += 1

                out.append(
                    self.render_dialog(
                        "\n".join(header_lines),
                        body_lines,
                    )
                )
            else:
                out.append(lines[i])

            i += 1

        return out

    def render_dialog(self, header, lines):
        participants = self.parse_participants(header)
        dialog_lines = self.parse_lines(lines)

        html = ['<div class="dialog">']

        for item in dialog_lines:
            kind = item["type"]

            if kind == "update":
                self.apply_update(participants, item)
                continue

            if kind == "system":
                html.append(self.render_system_line(item["text"]))
                continue

            p = participants.get(item["key"])
            if not p:
                html.append(self.render_system_line(item["text"]))
                continue

            html.append(
                self.render_line(
                    side=p["side"],
                    name=p.get("name"),
                    text=item["text"],
                    avatar=p.get("avatar"),
                )
            )

        html.append("</div>")
        return "\n".join(html)

    def parse_participants(self, header):
        participants = {}

        for raw in header.splitlines():
            raw = raw.strip()
            if not raw:
                continue

            m = self.PARTICIPANT_RE.match(raw)
            if not m:
                continue

            key = m.group("key").strip()
            side = m.group("side")
            opts_raw = m.group("opts") or ""

            opts = {}
            for k, v1, v2 in self.OPTION_RE.findall(opts_raw):
                opts[k] = v1 or v2

            participants[key] = {
                "side": side,
                **opts,
            }

        return participants

    def parse_lines(self, lines):
        result = []

        for line in lines:
            raw = line.strip()
            if not raw:
                continue

            m = self.UPDATE_RE.match(raw)
            if m:
                opts = {}
                for k, v1, v2 in self.OPTION_RE.findall(m.group(2)):
                    opts[k] = v1 or v2

                result.append(
                    {
                        "type": "update",
                        "key": m.group(1),
                        "opts": opts,
                    }
                )
                continue

            m = self.LINE_RE.match(raw)
            if m:
                result.append(
                    {
                        "type": "line",
                        "key": m.group(1).strip(),
                        "text": m.group(2).strip(),
                    }
                )
                continue

            result.append(
                {
                    "type": "system",
                    "text": raw,
                }
            )

        return result

    def apply_update(self, participants, item):
        p = participants.get(item["key"])
        if not p:
            return

        for k, v in item["opts"].items():
            p[k] = v

    def render_line(self, side, text, name=None, avatar=None):
        parts = [f'<div class="dialog-line {side}">']

        if avatar and side != "center":
            parts.append(
                f'<div class="dialog-avatar"><img src="{static_url(avatar)}"></div>'
            )

        parts.append('<div class="dialog-bubble">')

        if name:
            parts.append(f'<div class="dialog-name">{name}</div>')

        parts.append(f'<div class="dialog-text">{text}</div>')
        parts.append("</div></div>")

        return "\n".join(parts)

    def render_system_line(self, text):
        return (
            '<div class="dialog-line center">'
            '<div class="dialog-bubble system">'
            f'<div class="dialog-text">{text}</div>'
            "</div></div>"
        )
