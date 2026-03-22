(function () {
    const SVG_NS = "http://www.w3.org/2000/svg";
    const ROOT_SELECTOR = ".wiki-hierarchy";
    const DEFAULT_LINE_COLOR = "rgba(255, 166, 0, 0.54)";
    const ARROW_STUB = 5;
    const VERTICAL_ARROW_STUB = 5;
    let markerSequence = 0;
    let renderQueued = false;
    let resizeObserver = null;

    function round(value) {
        return Math.round(value * 10) / 10;
    }

    function parseEdges(root) {
        const raw = root.dataset.hierarchyEdges;
        if (!raw) {
            return [];
        }

        try {
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            console.warn("Failed to parse hierarchy edges", error);
            return [];
        }
    }

    function getNodeMap(root) {
        const map = new Map();

        root.querySelectorAll(".wiki-hierarchy-node[data-node-id]").forEach((node) => {
            map.set(node.dataset.nodeId, node);
        });

        return map;
    }

    function createSvgElement(name) {
        return document.createElementNS(SVG_NS, name);
    }

    function ensureSvg(root, canvas) {
        let svg = canvas.querySelector(".wiki-hierarchy-lines");
        if (svg) {
            return svg;
        }

        svg = createSvgElement("svg");
        svg.classList.add("wiki-hierarchy-lines");
        svg.setAttribute("aria-hidden", "true");

        const defs = createSvgElement("defs");
        const marker = createSvgElement("marker");
        const markerPath = createSvgElement("path");
        const markerId = `wiki-hierarchy-arrow-${++markerSequence}`;

        marker.setAttribute("id", markerId);
        marker.setAttribute("markerWidth", "8");
        marker.setAttribute("markerHeight", "8");
        marker.setAttribute("refX", "6.6");
        marker.setAttribute("refY", "4");
        marker.setAttribute("orient", "auto");
        marker.setAttribute("markerUnits", "userSpaceOnUse");

        markerPath.setAttribute("d", "M 0 0 L 8 4 L 0 8 z");
        marker.appendChild(markerPath);
        defs.appendChild(marker);
        svg.appendChild(defs);

        const layer = createSvgElement("g");
        layer.classList.add("wiki-hierarchy-lines-layer");
        svg.appendChild(layer);

        canvas.insertBefore(svg, canvas.firstChild);
        root.dataset.hierarchyMarkerId = markerId;
        return svg;
    }

    function getLineColor(root) {
        const value = getComputedStyle(root)
            .getPropertyValue("--wiki-hierarchy-line-color")
            .trim();

        return value || DEFAULT_LINE_COLOR;
    }

    function getBox(node, canvasRect) {
        const rect = node.getBoundingClientRect();
        return {
            left: rect.left - canvasRect.left,
            top: rect.top - canvasRect.top,
            right: rect.right - canvasRect.left,
            bottom: rect.bottom - canvasRect.top,
            width: rect.width,
            height: rect.height,
        };
    }

    function getCenterX(box) {
        return box.left + box.width / 2;
    }

    function getCenterY(box) {
        return box.top + box.height / 2;
    }

    function appendPath(layer, markerId, lineColor, pathData, cssClass, withArrow) {
        const path = createSvgElement("path");
        path.classList.add("wiki-hierarchy-line");

        if (cssClass) {
            path.classList.add(cssClass);
        }

        path.setAttribute("d", pathData);
        path.setAttribute("stroke", lineColor);

        if (withArrow) {
            path.setAttribute("marker-end", `url(#${markerId})`);
        }

        layer.appendChild(path);
    }

    function appendPoint(layer, lineColor, x, y, cssClass) {
        return;
    }

    function getChildStubX(childBox) {
        return round(childBox.left - ARROW_STUB);
    }

    function getChildTopStubY(childBox, stubLength = VERTICAL_ARROW_STUB) {
        return round(childBox.top - stubLength);
    }

    function buildHorizontalBusPath(parentBox, childBox) {
        const startX = round(parentBox.right);
        const startY = round(getCenterY(parentBox));
        const endX = getChildStubX(childBox);
        const endY = round(getCenterY(childBox));

        if (Math.abs(startY - endY) < 2) {
            return `M ${startX} ${startY} H ${endX}`;
        }

        const midX = round(startX + Math.max(14, (endX - startX) / 2));
        return `M ${startX} ${startY} H ${midX} V ${endY} H ${endX}`;
    }

    function appendArrowStub(layer, markerId, lineColor, childBox, y, cssClass) {
        const childStubX = getChildStubX(childBox);
        const childX = round(childBox.left);
        const childY = round(y);

        appendPath(
            layer,
            markerId,
            lineColor,
            `M ${childStubX} ${childY} H ${childX}`,
            cssClass,
            true
        );
    }

    function appendVerticalArrowStub(
        layer,
        markerId,
        lineColor,
        childBox,
        cssClass,
        stubLength = VERTICAL_ARROW_STUB
    ) {
        const childX = round(getCenterX(childBox));
        const childStubY = getChildTopStubY(childBox, stubLength);
        const childTop = round(childBox.top);

        appendPath(
            layer,
            markerId,
            lineColor,
            `M ${childX} ${childStubY} V ${childTop}`,
            cssClass,
            true
        );
    }

    function renderDirectArrow(layer, markerId, lineColor, parentBox, childBox, cssClass) {
        appendPoint(
            layer,
            lineColor,
            parentBox.right,
            getCenterY(parentBox),
            "is-source"
        );
        appendPath(
            layer,
            markerId,
            lineColor,
            buildHorizontalBusPath(parentBox, childBox),
            "is-trunk",
            false
        );
        appendArrowStub(
            layer,
            markerId,
            lineColor,
            childBox,
            getCenterY(childBox),
            cssClass
        );
    }

    function groupAttachmentEdges(edges) {
        const groups = new Map();

        edges.forEach((edge) => {
            if (edge.kind === "chain" || edge.kind === "merge") {
                return;
            }

            if (!groups.has(edge.from)) {
                groups.set(edge.from, []);
            }

            groups.get(edge.from).push(edge);
        });

        return groups;
    }

    function groupMergeEdgesByTarget(edges) {
        const mergeTargets = new Set(
            edges
                .filter((edge) => edge.kind === "merge")
                .map((edge) => edge.to)
        );
        const groups = new Map();

        if (!mergeTargets.size) {
            return groups;
        }

        edges.forEach((edge) => {
            if (!mergeTargets.has(edge.to)) {
                return;
            }

            if (
                edge.kind !== "chain" &&
                edge.kind !== "branch" &&
                edge.kind !== "sequence" &&
                edge.kind !== "merge"
            ) {
                return;
            }

            if (!groups.has(edge.to)) {
                groups.set(edge.to, []);
            }

            groups.get(edge.to).push(edge);
        });

        return groups;
    }

    function renderMergeGroup(layer, markerId, lineColor, items) {
        if (!items.length) {
            return;
        }

        if (items.length === 1) {
            renderDirectArrow(
                layer,
                markerId,
                lineColor,
                items[0].parentBox,
                items[0].childBox,
                "is-merge"
            );
            return;
        }

        const targetBox = items[0].childBox;
        const targetY = round(getCenterY(targetBox));
        const targetStubX = getChildStubX(targetBox);
        const sourceRights = items.map((item) => round(item.parentBox.right));
        const sourceYs = items.map((item) => round(getCenterY(item.parentBox)));
        const sourceMaxX = Math.max(...sourceRights);
        const mergeX = round(
            Math.min(
                targetStubX - 12,
                sourceMaxX + Math.max(20, (targetStubX - sourceMaxX) / 2)
            )
        );
        const minY = Math.min(targetY, ...sourceYs);
        const maxY = Math.max(targetY, ...sourceYs);

        appendPath(
            layer,
            markerId,
            lineColor,
            `M ${mergeX} ${minY} V ${maxY}`,
            "is-trunk",
            false
        );

        items.forEach((item) => {
            const startX = round(item.parentBox.right);
            const startY = round(getCenterY(item.parentBox));

            if (Math.abs(mergeX - startX) >= 2) {
                appendPath(
                    layer,
                    markerId,
                    lineColor,
                    `M ${startX} ${startY} H ${mergeX}`,
                    "is-trunk",
                    false
                );
            }
        });

        if (Math.abs(targetStubX - mergeX) >= 2) {
            appendPath(
                layer,
                markerId,
                lineColor,
                `M ${mergeX} ${targetY} H ${targetStubX}`,
                "is-trunk",
                false
            );
        }

        appendArrowStub(
            layer,
            markerId,
            lineColor,
            targetBox,
            targetY,
            "is-merge"
        );
    }

    function renderBranchGroup(layer, markerId, lineColor, items) {
        if (!items.length) {
            return;
        }

        const parentBox = items[0].parentBox;
        const startX = round(parentBox.right);
        const startY = round(getCenterY(parentBox));

        if (items.length === 1) {
            renderDirectArrow(
                layer,
                markerId,
                lineColor,
                parentBox,
                items[0].childBox,
                "is-attachment"
            );
            return;
        }

        const sorted = [...items].sort((left, right) => {
            if (left.childBox.top !== right.childBox.top) {
                return left.childBox.top - right.childBox.top;
            }

            return left.childBox.left - right.childBox.left;
        });

        const childLeft = Math.min(...sorted.map((item) => item.childBox.left));
        const childYs = sorted.map((item) => round(getCenterY(item.childBox)));
        const minY = Math.min(startY, ...childYs);
        const maxY = Math.max(startY, ...childYs);
        const trunkX = round(
            Math.min(
                childLeft - ARROW_STUB - 10,
                startX + Math.max(18, (childLeft - startX) / 2)
            )
        );

        appendPoint(layer, lineColor, startX, startY, "is-source");
        if (Math.abs(trunkX - startX) >= 2) {
            appendPath(
                layer,
                markerId,
                lineColor,
                `M ${startX} ${startY} H ${trunkX}`,
                "is-trunk",
                false
            );
        }
        appendPoint(layer, lineColor, trunkX, startY, "is-junction");
        appendPath(
            layer,
            markerId,
            lineColor,
            `M ${trunkX} ${minY} V ${maxY}`,
            "is-trunk",
            false
        );

        sorted.forEach((item) => {
            const childY = round(getCenterY(item.childBox));
            const childStubX = round(item.childBox.left - ARROW_STUB);

            appendPath(
                layer,
                markerId,
                lineColor,
                `M ${trunkX} ${childY} H ${childStubX}`,
                "is-trunk",
                false
            );

            appendArrowStub(
                layer,
                markerId,
                lineColor,
                item.childBox,
                childY,
                "is-attachment"
            );
        });
    }

    function getSequenceBusX(parentBox, items) {
        const startX = round(parentBox.right);
        const minChildLeft = Math.min(...items.map((item) => item.childBox.left));
        const minChildCenter = Math.min(
            ...items.map((item) => round(getCenterX(item.childBox)))
        );
        const lowerBound = startX + 14;
        const upperBound = Math.min(minChildLeft - 10, minChildCenter - 14);

        if (upperBound <= lowerBound) {
            return round(startX + Math.max(10, (minChildCenter - startX) / 2));
        }

        const preferred = startX + Math.max(18, Math.min((minChildLeft - startX) * 0.38, 34));
        return round(Math.min(Math.max(preferred, lowerBound), upperBound));
    }

    function renderSequenceGroup(layer, markerId, lineColor, items) {
        if (!items.length) {
            return;
        }

        const parentBox = items[0].parentBox;
        const startX = round(parentBox.right);
        const startY = round(getCenterY(parentBox));
        const busX = getSequenceBusX(parentBox, items);

        if (items.length === 1) {
            const childBox = items[0].childBox;
            const childX = round(getCenterX(childBox));
            const childStubY = getChildTopStubY(childBox);

            appendPoint(
                layer,
                lineColor,
                startX,
                startY,
                "is-source"
            );

            if (Math.abs(busX - startX) >= 2) {
                appendPath(
                    layer,
                    markerId,
                    lineColor,
                    `M ${startX} ${startY} H ${busX}`,
                    "is-trunk",
                    false
                );
            }
            if (Math.abs(childX - busX) >= 2) {
                appendPath(
                    layer,
                    markerId,
                    lineColor,
                    `M ${busX} ${startY} H ${childX}`,
                    "is-trunk",
                    false
                );
            }
            if (Math.abs(childStubY - startY) >= 2) {
                appendPath(
                    layer,
                    markerId,
                    lineColor,
                    `M ${childX} ${startY} V ${childStubY}`,
                    "is-trunk",
                    false
                );
            }
            appendVerticalArrowStub(
                layer,
                markerId,
                lineColor,
                childBox,
                "is-attachment"
            );
            return;
        }

        const sorted = [...items].sort(
            (left, right) => left.childBox.left - right.childBox.left
        );
        const childXs = sorted.map((item) => round(getCenterX(item.childBox)));
        const maxX = Math.max(...childXs);

        appendPoint(layer, lineColor, startX, startY, "is-source");
        if (Math.abs(busX - startX) >= 2) {
            appendPath(
                layer,
                markerId,
                lineColor,
                `M ${startX} ${startY} H ${busX}`,
                "is-trunk",
                false
            );
        }
        if (Math.abs(maxX - busX) >= 2) {
            appendPath(
                layer,
                markerId,
                lineColor,
                `M ${busX} ${startY} H ${maxX}`,
                "is-trunk",
                false
            );
        }

        appendPoint(layer, lineColor, busX, startY, "is-junction");

        sorted.forEach((item) => {
            const childX = round(getCenterX(item.childBox));
            const childStubY = getChildTopStubY(item.childBox);

            if (Math.abs(childX - startX) >= 2) {
                appendPoint(layer, lineColor, childX, startY, "is-junction");
            }
            if (Math.abs(childStubY - startY) >= 2) {
                appendPath(
                    layer,
                    markerId,
                    lineColor,
                    `M ${childX} ${startY} V ${childStubY}`,
                    "is-trunk",
                    false
                );
            }

            appendVerticalArrowStub(
                layer,
                markerId,
                lineColor,
                item.childBox,
                "is-attachment"
            );
        });
    }

    function renderHierarchy(root) {
        const canvas = root.querySelector(".wiki-hierarchy-canvas");
        const tree = root.querySelector(".wiki-hierarchy-tree");
        if (!canvas || !tree) {
            return;
        }

        const edges = parseEdges(root);
        if (!edges.length) {
            const existingSvg = canvas.querySelector(".wiki-hierarchy-lines");
            if (existingSvg) {
                existingSvg.remove();
            }
            return;
        }

        const svg = ensureSvg(root, canvas);
        const layer = svg.querySelector(".wiki-hierarchy-lines-layer");
        const markerPath = svg.querySelector("marker path");
        const markerId = root.dataset.hierarchyMarkerId;
        const lineColor = getLineColor(root);
        const nodeMap = getNodeMap(root);
        const canvasRect = canvas.getBoundingClientRect();

        const width = Math.ceil(
            Math.max(
                canvas.scrollWidth,
                tree.scrollWidth,
                tree.getBoundingClientRect().width
            )
        );
        const height = Math.ceil(
            Math.max(
                canvas.scrollHeight,
                tree.scrollHeight,
                tree.getBoundingClientRect().height
            )
        );

        svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
        svg.setAttribute("width", String(width));
        svg.setAttribute("height", String(height));

        if (markerPath) {
            markerPath.setAttribute("fill", lineColor);
        }

        layer.replaceChildren();
        const mergeGroups = groupMergeEdgesByTarget(edges);
        const mergedTargets = new Set(mergeGroups.keys());

        edges.forEach((edge) => {
            if (edge.kind !== "chain") {
                return;
            }

            if (mergedTargets.has(edge.to)) {
                return;
            }

            const parentNode = nodeMap.get(edge.from);
            const childNode = nodeMap.get(edge.to);
            if (!parentNode || !childNode) {
                return;
            }

            const parentBox = getBox(parentNode, canvasRect);
            const childBox = getBox(childNode, canvasRect);
            if (!parentBox.width || !childBox.width) {
                return;
            }

            renderDirectArrow(
                layer,
                markerId,
                lineColor,
                parentBox,
                childBox,
                "is-chain"
            );
        });

        groupAttachmentEdges(edges).forEach((groupEdges) => {
            const items = groupEdges
                .filter((edge) => !mergedTargets.has(edge.to))
                .map((edge) => {
                    const parentNode = nodeMap.get(edge.from);
                    const childNode = nodeMap.get(edge.to);
                    if (!parentNode || !childNode) {
                        return null;
                    }

                    const parentBox = getBox(parentNode, canvasRect);
                    const childBox = getBox(childNode, canvasRect);
                    if (!parentBox.width || !childBox.width) {
                        return null;
                    }

                    return {
                        kind: edge.kind,
                        parentBox,
                        childBox,
                    };
                })
                .filter(Boolean);

            if (!items.length) {
                return;
            }

            if (items[0].kind === "sequence") {
                renderSequenceGroup(layer, markerId, lineColor, items);
                return;
            }

            renderBranchGroup(layer, markerId, lineColor, items);
        });

        mergeGroups.forEach((groupEdges) => {
            const items = groupEdges
                .map((edge) => {
                    const parentNode = nodeMap.get(edge.from);
                    const childNode = nodeMap.get(edge.to);
                    if (!parentNode || !childNode) {
                        return null;
                    }

                    const parentBox = getBox(parentNode, canvasRect);
                    const childBox = getBox(childNode, canvasRect);
                    if (!parentBox.width || !childBox.width) {
                        return null;
                    }

                    return {
                        kind: edge.kind,
                        parentBox,
                        childBox,
                    };
                })
                .filter(Boolean);

            if (!items.length) {
                return;
            }

            renderMergeGroup(layer, markerId, lineColor, items);
        });
    }

    function renderAll() {
        renderQueued = false;
        document.querySelectorAll(ROOT_SELECTOR).forEach(renderHierarchy);
    }

    function scheduleRender() {
        if (renderQueued) {
            return;
        }

        renderQueued = true;
        window.requestAnimationFrame(renderAll);
    }

    function setupObservers() {
        if (resizeObserver) {
            return;
        }

        resizeObserver = new ResizeObserver(() => {
            scheduleRender();
        });

        document.querySelectorAll(ROOT_SELECTOR).forEach((root) => {
            const canvas = root.querySelector(".wiki-hierarchy-canvas");
            const tree = root.querySelector(".wiki-hierarchy-tree");

            if (canvas) {
                resizeObserver.observe(canvas);
            }

            if (tree) {
                resizeObserver.observe(tree);
            }
        });
    }

    window.addEventListener("resize", scheduleRender, { passive: true });
    window.addEventListener("pageshow", scheduleRender);
    document.addEventListener("DOMContentLoaded", () => {
        setupObservers();
        scheduleRender();

        if (
            document.fonts &&
            document.fonts.ready &&
            typeof document.fonts.ready.then === "function"
        ) {
            document.fonts.ready.then(scheduleRender);
        }
    });
})();
