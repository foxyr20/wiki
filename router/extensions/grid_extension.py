import re
import xml.etree.ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension

from .block_utils import find_match_in_lines, has_matching_line, parse_prefix_blocks


class GridExtension(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(
            GridBlockProcessor(md.parser),
            "wiki_grid",
            15,
        )


class GridBlockProcessor(BlockProcessor):
    START_RE = re.compile(r"^\s*!grid(?:\[(?P<cols>\d+)\])?\s*$")
    STEP_RE = re.compile(r"^\s*!grid_step(?:\[(?P<step>\d+)\])?\s*$")
    END_RE = re.compile(r"^\s*!grid_end\s*$")

    def test(self, parent, block):
        return has_matching_line(block, self.START_RE)

    def run(self, parent, blocks):
        first = blocks.pop(0)
        first_lines = first.splitlines()
        start_idx, start_match = find_match_in_lines(first_lines, self.START_RE)

        if start_idx is None:
            return True

        parse_prefix_blocks(self.parser, parent, first_lines[:start_idx])

        cols = (
            int(start_match.group("cols"))
            if start_match and start_match.group("cols")
            else 3
        )

        grid = etree.SubElement(parent, "div")
        grid.set("class", "wiki-grid")
        grid.set("style", f"--grid-cols:{cols};")

        buffer: list[str] = []
        cell_index = 0

        def flush_cell():
            nonlocal cell_index

            if not buffer:
                return

            col = (cell_index % cols) + 1
            row = (cell_index // cols) + 1

            cell = etree.SubElement(grid, "div")
            cell.set("class", "wiki-grid-cell")
            cell.set("style", f"grid-column: {col}; grid-row: {row};")

            self.parser.parseBlocks(cell, buffer)
            buffer.clear()

        start_tail = "\n".join(first_lines[start_idx + 1 :]).strip("\n")
        if start_tail.strip():
            blocks.insert(0, start_tail)

        while blocks:
            b = blocks.pop(0)
            tokens = self._tokenize_block(b)
            i = 0

            while i < len(tokens):
                kind, value = tokens[i]

                if kind == "end":
                    self._push_tokens_back(blocks, tokens[i + 1 :])
                    flush_cell()
                    return True

                if kind == "step":
                    m_step = self.STEP_RE.match(value.strip())
                    flush_cell()

                    step = int(m_step.group("step") or 1) if m_step else 1
                    cell_index += step
                    i += 1
                    continue

                if value.strip():
                    buffer.append(value)

                i += 1

        flush_cell()
        return True

    def _tokenize_block(self, block: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        content: list[str] = []

        def flush_content() -> None:
            if content and any(line.strip() for line in content):
                tokens.append(("content", "\n".join(content)))
            content.clear()

        for line in block.splitlines():
            stripped = line.strip()

            if self.END_RE.match(stripped):
                flush_content()
                tokens.append(("end", line))
                continue

            if self.STEP_RE.match(stripped):
                flush_content()
                tokens.append(("step", line))
                continue

            content.append(line)

        flush_content()
        return tokens

    def _push_tokens_back(self, blocks, tokens: list[tuple[str, str]]) -> None:
        tail_blocks: list[str] = []

        for kind, value in tokens:
            if kind == "content":
                if value.strip():
                    tail_blocks.append(value)
                continue

            raw = value.strip()
            if raw:
                tail_blocks.append(raw)

        for block in reversed(tail_blocks):
            blocks.insert(0, block)
