import re
import xml.etree.ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension


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
        return bool(self.START_RE.match(block.strip()))

    def run(self, parent, blocks):
        first = blocks.pop(0)
        m = self.START_RE.match(first.strip())

        cols = int(m.group("cols")) if m and m.group("cols") else 3

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

        while blocks:
            b = blocks.pop(0)
            line = b.strip()

            if self.END_RE.match(line):
                break

            m_step = self.STEP_RE.match(line)
            if m_step:
                flush_cell()

                step = int(m_step.group("step") or 1)
                cell_index += step

                continue

            buffer.append(b)

        flush_cell()
        return True
