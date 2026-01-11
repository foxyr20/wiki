import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class FolderTreeExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(FolderTreePreprocessor(md), "foldertree", 25)


class FolderTreePreprocessor(Preprocessor):
    RE_START = re.compile(r"^!folder\[\s*$")
    RE_END = re.compile(r"^\s*\]\s*$")

    def run(self, lines):
        new_lines = []
        i = 0

        while i < len(lines):
            if self.RE_START.match(lines[i]):
                i += 1
                paths = []
                while i < len(lines) and not self.RE_END.match(lines[i]):
                    line = lines[i].strip()
                    if line:
                        paths.append(line)
                    i += 1
                i += 1

                tree = {}
                for path_str in paths:
                    parts = path_str.strip("/").split("/")
                    cur = tree
                    for part in parts:
                        cur = cur.setdefault(part, {})

                def render(node: dict, prefix: str = "") -> list[str]:
                    out = []
                    items = sorted(
                        node.items(),
                        key=lambda item: (0 if item[1] else 1, item[0].lower()),
                    )
                    for idx, (name, sub) in enumerate(items):
                        last = idx == len(items) - 1
                        connector = "└── " if last else "├── "
                        display = name + ("/" if sub else "")
                        out.append(f"{prefix}{connector}{display}")
                        ext = "    " if last else "│   "
                        out.extend(render(sub, prefix + ext))
                    return out

                roots = set(p.strip("/").split("/")[0] for p in paths)
                if len(roots) == 1:
                    root = roots.pop()
                    lines_tree = [f"/{root}"]
                    for line in render(tree[root], ""):
                        lines_tree.append(" " + line)
                else:
                    lines_tree = render(tree, "")

                new_lines.append('<div class="foldertree">')
                new_lines.append("<pre>")
                new_lines.extend(lines_tree)
                new_lines.append("</pre>")
                new_lines.append("</div>")
            else:
                new_lines.append(lines[i])
                i += 1

        return new_lines
