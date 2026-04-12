from __future__ import annotations

import html
import json
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from template_env import static_url

from .block_utils import find_end_index

log = logging.getLogger(__name__)


@dataclass(slots=True)
class HierarchyNode:
    node_id: str
    title: str
    subtitle: str
    image: str | None
    order: int
    explicit: bool


@dataclass(slots=True)
class HierarchyAttachment:
    origin_id: str
    mode: str
    blocks: list["HierarchyBlock"]


@dataclass(slots=True)
class HierarchyBlock:
    spine: list[str]
    attachments: dict[str, list[HierarchyAttachment]]


class HierarchyExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {
            "branch_threshold": [
                3,
                "Максимум дочерних узлов, который ещё можно показывать последовательной группой",
            ],
            "max_chain_length": [
                4,
                "Максимальная длина вертикальной цепочки до выноса продолжения в отдельную ветку",
            ],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        md.preprocessors.register(
            HierarchyPreprocessor(
                md,
                branch_threshold=int(self.getConfig("branch_threshold")),
                max_chain_length=int(self.getConfig("max_chain_length")),
            ),
            "hierarchy",
            23,
        )


class HierarchyPreprocessor(Preprocessor):
    START_RE = re.compile(r"^\s*!hierarchy\s*$")
    END_RE = re.compile(r"^\s*!hierarchy_end\s*$")
    EDGE_RE = re.compile(r"^\s*(?P<src>.+?)\s*-->\s*(?P<dst>.+?)\s*$")
    NODE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
    NODE_DECL_RE = re.compile(
        r'^(?P<id>[A-Za-z_][A-Za-z0-9_-]*)\s*\[\s*"(?P<label>(?:\\.|[^"\\])*)"\s*\]\s*$'
    )
    COMMENT_RE = re.compile(r"^\s*(#|//)")

    def __init__(
        self,
        md,
        *,
        branch_threshold: int,
        max_chain_length: int,
    ):
        super().__init__(md)
        self.branch_threshold = max(1, branch_threshold)
        self.max_chain_length = max(1, max_chain_length)

    def run(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        i = 0

        while i < len(lines):
            if not self.START_RE.match(lines[i]):
                out.append(lines[i])
                i += 1
                continue

            body_start = i + 1
            end_rel = find_end_index(lines[body_start:], self.END_RE)

            if end_rel is None:
                log.warning(
                    "Hierarchy block has no !hierarchy_end; source is kept as-is"
                )
                out.extend(lines[i:])
                break

            end_idx = body_start + end_rel
            body_lines = lines[body_start:end_idx]

            out.append(self._render_hierarchy_block(body_lines))
            i = end_idx + 1

        return out

    def _render_hierarchy_block(self, lines: list[str]) -> str:
        nodes: dict[str, HierarchyNode] = {}
        edges: list[tuple[str, str]] = []
        seen_edges: set[tuple[str, str]] = set()
        next_order = 0

        def register_node(token: str) -> str | None:
            nonlocal next_order

            parsed = self._parse_node_token(token)
            if parsed is None:
                return None

            node_id, title, subtitle, image, declared = parsed
            existing = nodes.get(node_id)

            if existing is None:
                nodes[node_id] = HierarchyNode(
                    node_id=node_id,
                    title=title or node_id,
                    subtitle=subtitle,
                    image=image,
                    order=next_order,
                    explicit=declared,
                )
                next_order += 1
                return node_id

            if declared:
                if not existing.explicit:
                    nodes[node_id] = HierarchyNode(
                        node_id=node_id,
                        title=title or node_id,
                        subtitle=subtitle,
                        image=image,
                        order=existing.order,
                        explicit=True,
                    )
                elif (existing.title, existing.subtitle, existing.image) != (
                    title or node_id,
                    subtitle,
                    image,
                ):
                    log.warning(
                        "Hierarchy node %r is declared multiple times; first declaration wins",
                        node_id,
                    )

            return node_id

        for raw_line in lines:
            line = raw_line.strip()

            if not line or self.COMMENT_RE.match(line):
                continue

            edge_match = self.EDGE_RE.match(line)
            if edge_match:
                src_id = register_node(edge_match.group("src"))
                dst_id = register_node(edge_match.group("dst"))

                if not src_id or not dst_id:
                    log.warning("Invalid hierarchy edge syntax ignored: %r", raw_line)
                    continue

                edge = (src_id, dst_id)
                if edge in seen_edges:
                    continue

                seen_edges.add(edge)
                edges.append(edge)
                continue

            if register_node(line) is None:
                log.warning("Invalid hierarchy line ignored: %r", raw_line)

        if not nodes:
            return (
                '<div class="wiki-hierarchy wiki-hierarchy-empty">'
                "Пустой блок иерархии."
                "</div>"
            )

        levels, incoming, _ = self._build_levels(nodes, edges)
        roots, layout_children = self._build_layout_tree(
            nodes=nodes,
            incoming=incoming,
            levels=levels,
        )

        root_blocks = [
            self._build_layout_block(
                node_id=root_id,
                layout_children=layout_children,
                chain_length=1,
            )
            for root_id in roots
        ]

        layout_edges = self._collect_layout_edges(root_blocks)
        layout_edge_pairs = {
            (edge["from"], edge["to"])
            for edge in layout_edges
        }
        merge_edges = [
            {
                "from": src,
                "to": dst,
                "kind": "merge",
            }
            for src, dst in edges
            if (src, dst) not in layout_edge_pairs
        ]

        edges_payload = html.escape(
            json.dumps(layout_edges + merge_edges, ensure_ascii=False),
            quote=True,
        )

        parts = [
            f'<div class="wiki-hierarchy" data-hierarchy-edges="{edges_payload}">',
            '  <div class="wiki-hierarchy-scroll">',
            '    <div class="wiki-hierarchy-canvas">',
            '      <div class="wiki-hierarchy-tree">',
        ]

        for block in root_blocks:
            parts.extend(
                self._render_layout_block(
                    block=block,
                    nodes=nodes,
                    incoming=incoming,
                    indent="        ",
                )
            )

        parts.extend(
            [
                "      </div>",
                "    </div>",
                "  </div>",
                "</div>",
            ]
        )

        return "\n".join(parts)

    def _build_layout_tree(
        self,
        *,
        nodes: dict[str, HierarchyNode],
        incoming: dict[str, list[str]],
        levels: dict[str, int],
    ) -> tuple[list[str], dict[str, list[str]]]:
        layout_children: dict[str, list[str]] = defaultdict(list)
        attached: set[str] = set()

        ordered_ids = [
            node_id
            for node_id, _ in sorted(nodes.items(), key=lambda item: item[1].order)
        ]

        for node_id in ordered_ids:
            parent_candidates = [
                parent
                for parent in incoming.get(node_id, [])
                if levels.get(parent, -1) < levels.get(node_id, 0)
            ]

            if not parent_candidates:
                continue

            parent_id = parent_candidates[0]
            layout_children[parent_id].append(node_id)
            attached.add(node_id)

        for parent_id in layout_children:
            layout_children[parent_id].sort(key=lambda child_id: nodes[child_id].order)

        roots = [node_id for node_id in ordered_ids if node_id not in attached]
        if not roots:
            roots = ordered_ids[:]

        return roots, layout_children

    def _build_layout_block(
        self,
        *,
        node_id: str,
        layout_children: dict[str, list[str]],
        chain_length: int,
    ) -> HierarchyBlock:
        spine = [node_id]
        attachments: dict[str, list[HierarchyAttachment]] = defaultdict(list)
        current_id = node_id
        current_chain_length = chain_length

        while True:
            children = layout_children.get(current_id, [])
            if not children:
                break

            if len(children) == 1 and current_chain_length < self.max_chain_length:
                child_id = children[0]
                current_id = child_id
                spine.append(current_id)
                current_chain_length += 1
                continue

            mode = "sequence" if len(children) <= self.branch_threshold else "branch"
            attachments[current_id].append(
                HierarchyAttachment(
                    origin_id=current_id,
                    mode=mode,
                    blocks=[
                        self._build_layout_block(
                            node_id=child_id,
                            layout_children=layout_children,
                            chain_length=1,
                        )
                        for child_id in children
                    ],
                )
            )
            break

        return HierarchyBlock(
            spine=spine,
            attachments=dict(attachments),
        )

    def _collect_layout_edges(
        self,
        blocks: list[HierarchyBlock],
    ) -> list[dict[str, str]]:
        edges: list[dict[str, str]] = []

        for block in blocks:
            for index in range(len(block.spine) - 1):
                edges.append(
                    {
                        "from": block.spine[index],
                        "to": block.spine[index + 1],
                        "kind": "chain",
                    }
                )

            for attachments in block.attachments.values():
                for attachment in attachments:
                    for child_block in attachment.blocks:
                        if not child_block.spine:
                            continue

                        edges.append(
                            {
                                "from": attachment.origin_id,
                                "to": child_block.spine[0],
                                "kind": attachment.mode,
                            }
                        )
                        edges.extend(self._collect_layout_edges([child_block]))

        return edges

    def _render_layout_block(
        self,
        *,
        block: HierarchyBlock,
        nodes: dict[str, HierarchyNode],
        incoming: dict[str, list[str]],
        indent: str,
    ) -> list[str]:
        anchor_id = block.spine[-1]
        attachments = block.attachments.get(anchor_id, [])
        block_classes = ["wiki-hierarchy-block"]
        body_mode = attachments[0].mode if attachments else None
        block_classes.append("has-attachments" if attachments else "leaf")
        if body_mode:
            block_classes.append(f"has-{body_mode}-body")

        parts = [f'{indent}<section class="{" ".join(block_classes)}">']
        parts.append(f'{indent}  <div class="wiki-hierarchy-spine">')

        for index, node_id in enumerate(block.spine):
            node = nodes[node_id]
            parents = incoming.get(node_id, [])
            spine_classes = ["wiki-hierarchy-spine-node"]
            if index == len(block.spine) - 1:
                spine_classes.append("is-anchor")

            parts.append(f'{indent}    <div class="{" ".join(spine_classes)}">')
            parts.append(f'{indent}      <div class="wiki-hierarchy-node-wrap">')
            parts.extend(
                self._render_node_card(
                    node=node,
                    parents=parents,
                    nodes=nodes,
                    indent=f"{indent}        ",
                )
            )
            parts.append(f"{indent}      </div>")
            parts.append(f"{indent}    </div>")

        parts.append(f"{indent}  </div>")

        if attachments:
            parts.append(
                f'{indent}  <div class="wiki-hierarchy-block-body is-{body_mode}">'
            )

            for attachment in attachments:
                group_classes = ["wiki-hierarchy-group", f"is-{attachment.mode}"]
                parts.append(f'{indent}    <div class="{" ".join(group_classes)}">')
                parts.append(f'{indent}      <div class="wiki-hierarchy-group-body">')

                for child_block in attachment.blocks:
                    parts.append(
                        f'{indent}        <div class="wiki-hierarchy-group-item">'
                    )
                    parts.extend(
                        self._render_layout_block(
                            block=child_block,
                            nodes=nodes,
                            incoming=incoming,
                            indent=f"{indent}          ",
                        )
                    )
                    parts.append(f"{indent}        </div>")

                parts.append(f"{indent}      </div>")
                parts.append(f"{indent}    </div>")

            parts.append(f"{indent}  </div>")

        parts.append(f"{indent}</section>")
        return parts

    def _parse_node_token(
        self,
        token: str,
    ) -> tuple[str, str, str, str | None, bool] | None:
        token = token.strip()
        if not token:
            return None

        declared = self.NODE_DECL_RE.match(token)
        if declared:
            node_id = declared.group("id")
            title, subtitle, image = self._parse_label_blob(
                declared.group("label"),
                node_id,
            )
            return node_id, title, subtitle, image, True

        if self.NODE_ID_RE.fullmatch(token):
            return token, token, "", None, False

        return None

    def _parse_label_blob(
        self,
        raw: str,
        node_id: str,
    ) -> tuple[str, str, str | None]:
        text = self._unescape_value(raw)
        fields = self._split_fields(text)

        if not fields:
            return node_id, "", None

        title = fields[0].strip() or node_id
        subtitle = fields[1].strip() if len(fields) > 1 else ""
        image = fields[2].strip() if len(fields) > 2 else ""
        image = image or None

        if len(fields) > 3:
            log.warning(
                "Hierarchy node %r has extra fields in label; only first 3 are used",
                node_id,
            )

        return title, subtitle, image

    def _split_fields(self, value: str) -> list[str]:
        out: list[str] = []
        current: list[str] = []
        escaped = False

        for ch in value:
            if escaped:
                current.append(ch)
                escaped = False
                continue

            if ch == "\\":
                escaped = True
                continue

            if ch == "|":
                out.append("".join(current))
                current = []
                continue

            current.append(ch)

        if escaped:
            current.append("\\")

        out.append("".join(current))
        return out

    def _unescape_value(self, value: str) -> str:
        return (
            value.replace(r"\\", "\\")
            .replace(r"\"", '"')
            .replace(r"\n", "\n")
            .replace(r"\t", "\t")
        )

    def _build_levels(
        self,
        nodes: dict[str, HierarchyNode],
        edges: list[tuple[str, str]],
    ) -> tuple[dict[str, int], dict[str, list[str]], dict[str, list[str]]]:
        incoming: dict[str, list[str]] = defaultdict(list)
        outgoing: dict[str, list[str]] = defaultdict(list)
        indegree = {node_id: 0 for node_id in nodes}

        for src, dst in edges:
            outgoing[src].append(dst)
            incoming[dst].append(src)
            indegree[dst] = indegree.get(dst, 0) + 1

        for src, children in outgoing.items():
            children.sort(key=lambda child_id: nodes[child_id].order)
            outgoing[src] = children

        for dst, parents in incoming.items():
            parents.sort(key=lambda parent_id: nodes[parent_id].order)
            incoming[dst] = parents

        levels = {node_id: 0 for node_id in nodes}
        queue = deque(
            sorted(
                (node_id for node_id, degree in indegree.items() if degree == 0),
                key=lambda node_id: nodes[node_id].order,
            )
        )

        visited: set[str] = set()

        while queue:
            node_id = queue.popleft()
            visited.add(node_id)

            for child_id in outgoing.get(node_id, []):
                levels[child_id] = max(levels[child_id], levels[node_id] + 1)
                indegree[child_id] -= 1

                if indegree[child_id] == 0:
                    queue.append(child_id)

        if len(visited) != len(nodes):
            cyclic = sorted(
                (node_id for node_id in nodes if node_id not in visited),
                key=lambda node_id: nodes[node_id].order,
            )
            log.warning(
                "Hierarchy has cycle or disconnected loop (%s); levels may be approximate",
                ", ".join(cyclic),
            )

            for node_id in cyclic:
                parent_level = 0
                for parent_id in incoming.get(node_id, []):
                    parent_level = max(parent_level, levels.get(parent_id, 0) + 1)
                levels[node_id] = max(levels.get(node_id, 0), parent_level)

        return levels, incoming, outgoing

    def _render_node_card(
        self,
        *,
        node: HierarchyNode,
        parents: list[str],
        nodes: dict[str, HierarchyNode],
        indent: str,
    ) -> list[str]:
        classes = ["wiki-hierarchy-node"]
        classes.append("has-image" if node.image else "no-image")
        if node.subtitle:
            classes.append("has-subtitle")

        parts = [
            f'{indent}<article class="{" ".join(classes)}" data-node-id="{html.escape(node.node_id, quote=True)}">'
        ]

        if node.image:
            source = node.image
            if not source.startswith(("http://", "https://")):
                source = static_url(source)

            parts.extend(
                [
                    f'{indent}  <div class="wiki-hierarchy-node-image-wrap">',
                    f'{indent}    <img class="wiki-hierarchy-node-image" src="{html.escape(source, quote=True)}" alt="" loading="lazy" decoding="async">',
                    f"{indent}  </div>",
                ]
            )

        parts.extend(
            [
                f'{indent}  <div class="wiki-hierarchy-node-body">',
                f'{indent}    <div class="wiki-hierarchy-node-title">{html.escape(node.title)}</div>',
            ]
        )

        if node.subtitle:
            parts.append(
                f'{indent}    <div class="wiki-hierarchy-node-subtitle">{html.escape(node.subtitle)}</div>'
            )


        parts.extend(
            [
                f"{indent}  </div>",
                f"{indent}</article>",
            ]
        )

        return parts
