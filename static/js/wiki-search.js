let WIKI_INDEX = null;

async function loadWikiIndex() {
    const storedHash = localStorage.getItem("wiki-index-hash") || "";
    const storedIndex = localStorage.getItem("wiki-index");

    try {
        const res = await fetch("/wiki/search/index", {
            headers: {
                "If-None-Match": storedHash
            }
        });

        if (res.status === 304) {
            if (storedIndex) {
                WIKI_INDEX = JSON.parse(storedIndex);
                return;
            }

            const retry = await fetch("/wiki/search/index");
            if (!retry.ok) return;

            const data = await retry.json();
            WIKI_INDEX = data;
            localStorage.setItem("wiki-index", JSON.stringify(data));
            return;
        }

        if (!res.ok) {
            console.error("Failed to load wiki index:", res.status);
            return;
        }

        const etag = res.headers.get("ETag");
        const data = await res.json();

        localStorage.setItem("wiki-index", JSON.stringify(data));
        if (etag) {
            localStorage.setItem("wiki-index-hash", etag);
        }

        WIKI_INDEX = data;
    } catch (err) {
        console.error("Wiki index load error:", err);
    }
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parseQueryWords(query) {
    return query
        .toLowerCase()
        .split(/\s+/)
        .filter(w => w.length >= 2);
}

function makeAnchor(text) {
    return text
        .toLowerCase()
        .trim()
        .replace(/[^\p{L}\p{N}\s-]/gu, "")
        .replace(/\s+/g, "-");
}

function makeSnippet(text, words, radius = 40) {
    const lower = text.toLowerCase();

    for (const w of words) {
        const idx = lower.indexOf(w);
        if (idx === -1) continue;

        const start = Math.max(0, idx - radius);
        const end = Math.min(text.length, idx + w.length + radius);

        let snippet = text.slice(start, end);
        snippet = escapeHtml(snippet);

        const re = new RegExp(`(${escapeRegExp(w)})`, "ig");
        snippet = snippet.replace(
            re,
            `<span class="wiki-search-highlight">$1</span>`
        );

        if (start > 0) snippet = "…" + snippet;
        if (end < text.length) snippet += "…";

        return snippet;
    }

    return "";
}

function searchWiki(query) {
    if (!WIKI_INDEX || !query) return [];

    const words = parseQueryWords(query);

    if (!words.length) return [];

    const results = [];

    for (const page of WIKI_INDEX.pages) {
        const sections = page.sections || [];

        for (let i = 0; i < sections.length; i++) {
            const sec = sections[i];
            const hay = sec.text.toLowerCase();

            let score = 0;
            for (const w of words) {
                if (hay.includes(w)) score++;
            }

            if (score === 0) continue;

            if (sec.kind === "heading") score += 5;
            if (sec.kind === "dialog") score += 1;

            results.push({
                page,
                section: sec,
                sectionIndex: i,
                score
            });
        }
    }

    results.sort((a, b) => b.score - a.score);
    return results.slice(0, 10);
}

function countOccurrences(text, needle) {
    if (!needle) return 0;

    let count = 0;
    let pos = 0;
    while (true) {
        const idx = text.indexOf(needle, pos);
        if (idx === -1) break;
        count += 1;
        pos = idx + needle.length;
    }
    return count;
}

function pickFocusWord(sectionText, words) {
    const lower = (sectionText || "").toLowerCase();
    let bestWord = "";
    let bestIdx = Number.MAX_SAFE_INTEGER;

    for (const w of words) {
        const idx = lower.indexOf(w);
        if (idx !== -1 && idx < bestIdx) {
            bestIdx = idx;
            bestWord = w;
        }
    }

    return bestWord || words[0] || "";
}

function computeHitOrdinal(page, sectionIndex, focusWord) {
    if (!focusWord) return 1;

    const sections = page.sections || [];
    let total = 0;

    for (let i = 0; i < sections.length; i++) {
        const text = (sections[i].text || "").toLowerCase();
        if (i < sectionIndex) {
            total += countOccurrences(text, focusWord);
            continue;
        }

        if (i === sectionIndex) {
            const idx = text.indexOf(focusWord);
            if (idx === -1) return Math.max(1, total + 1);

            total += countOccurrences(
                text.slice(0, idx + focusWord.length),
                focusWord
            );
            return Math.max(1, total);
        }
    }

    return Math.max(1, total + 1);
}

function makeResultUrl(result, query) {
    const base = `/wiki/${result.page.path}`;
    const idx = result.sectionIndex;
    const words = parseQueryWords(query);
    const focusWord = pickFocusWord(result.section.text, words);
    const hitOrdinal = computeHitOrdinal(result.page, idx, focusWord);

    const url = new URL(base, window.location.origin);
    if (query) {
        url.searchParams.set("q", query);
    }
    if (focusWord) {
        url.searchParams.set("w", focusWord);
        url.searchParams.set("hit", String(hitOrdinal));
    }
    url.searchParams.set("s", String(idx));

    if (result.section.kind === "heading") {
        url.hash = encodeURIComponent(makeAnchor(result.section.text));
        return url.pathname + url.search + url.hash;
    }

    return url.pathname + url.search;
}

function clearResults(box) {
    box.innerHTML = "";
    box.style.display = "none";
}

function renderResults(results, box, query) {
    box.innerHTML = "";

    if (!results.length) {
        box.style.display = "none";
        return;
    }

    const words = parseQueryWords(query);

    for (const r of results) {
        const item = document.createElement("div");
        item.className = "wiki-search-item";

        const title = document.createElement("div");
        title.className = "wiki-search-title";
        title.textContent = r.page.title;

        const kind = document.createElement("div");
        kind.className = "wiki-search-kind";

        if (r.section.kind === "heading") {
            kind.textContent = "Заголовок";
        } else if (r.section.kind === "dialog") {
            kind.textContent = `Диалог: ${r.section.speaker || "—"}`;
        } else {
            kind.textContent = "Текст";
        }

        const snippet = document.createElement("div");
        snippet.className = "wiki-search-snippet";
        snippet.innerHTML = makeSnippet(r.section.text, words);

        const url = makeResultUrl(r, query);

        item.appendChild(title);
        item.appendChild(kind);
        if (snippet.innerHTML) {
            item.appendChild(snippet);
        }

        item.addEventListener("click", () => {
            window.location.href = url;
        });

        box.appendChild(item);
    }

    box.style.display = "block";
}

function highlightWordsInContent(words) {
    const container = document.querySelector(".content");
    if (!container || !words.length) return [];

    const orderedWords = [...words].sort((a, b) => b.length - a.length);
    const rx = new RegExp(
        `(${orderedWords.map(w => escapeRegExp(w)).join("|")})`,
        "giu"
    );

    const walker = document.createTreeWalker(
        container,
        NodeFilter.SHOW_TEXT,
        {
            acceptNode(node) {
                if (!node.nodeValue || !node.nodeValue.trim()) {
                    return NodeFilter.FILTER_REJECT;
                }

                const parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;
                if (parent.closest(".wiki-search-results")) return NodeFilter.FILTER_REJECT;
                if (parent.classList.contains("wiki-page-hit")) return NodeFilter.FILTER_REJECT;

                const tag = parent.tagName;
                if (
                    tag === "SCRIPT" ||
                    tag === "STYLE" ||
                    tag === "NOSCRIPT" ||
                    tag === "PRE" ||
                    tag === "CODE" ||
                    tag === "TEXTAREA" ||
                    tag === "INPUT"
                ) {
                    return NodeFilter.FILTER_REJECT;
                }

                return NodeFilter.FILTER_ACCEPT;
            }
        }
    );

    const nodes = [];
    while (walker.nextNode()) {
        nodes.push(walker.currentNode);
    }

    const marks = [];

    for (const node of nodes) {
        const text = node.nodeValue;
        if (!text) continue;

        rx.lastIndex = 0;
        if (!rx.test(text)) continue;

        const frag = document.createDocumentFragment();
        let lastIndex = 0;
        rx.lastIndex = 0;

        let match;
        while ((match = rx.exec(text)) !== null) {
            const idx = match.index;
            if (idx > lastIndex) {
                frag.appendChild(document.createTextNode(text.slice(lastIndex, idx)));
            }

            const span = document.createElement("span");
            span.className = "wiki-page-hit";
            span.dataset.word = match[0].toLowerCase();
            span.textContent = match[0];
            frag.appendChild(span);
            marks.push(span);

            lastIndex = idx + match[0].length;
        }

        if (lastIndex < text.length) {
            frag.appendChild(document.createTextNode(text.slice(lastIndex)));
        }

        node.parentNode.replaceChild(frag, node);
    }

    return marks;
}

function applySearchHighlightFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const query = (params.get("q") || "").trim();
    if (!query) return;

    const words = parseQueryWords(query);
    if (!words.length) return;

    const marks = highlightWordsInContent(words);
    if (!marks.length) return;

    const focusWord = (params.get("w") || "").toLowerCase();
    const hit = Math.max(1, Number.parseInt(params.get("hit") || "1", 10));

    let target = null;
    if (focusWord) {
        const scoped = marks.filter(m => (m.dataset.word || "") === focusWord);
        if (scoped.length) {
            target = scoped[Math.min(hit - 1, scoped.length - 1)];
        }
    }

    if (!target) {
        target = marks[0];
    }

    requestAnimationFrame(() => {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("wiki-page-hit-active");
        setTimeout(() => {
            target.classList.remove("wiki-page-hit-active");
        }, 1600);
    });
}

function initWikiSearch() {
    const input = document.querySelector(".wiki-search input");
    if (!input) return;

    const resultsBox = document.createElement("div");
    resultsBox.className = "wiki-search-results";
    resultsBox.style.display = "none";

    input.parentNode.appendChild(resultsBox);

    input.addEventListener("input", () => {
        const query = input.value.trim();

        if (!query) {
            clearResults(resultsBox);
            return;
        }

        const results = searchWiki(query);
        renderResults(results, resultsBox, query);
    });

    document.addEventListener("click", (e) => {
        if (!input.contains(e.target) && !resultsBox.contains(e.target)) {
            clearResults(resultsBox);
        }
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    applySearchHighlightFromUrl();
    await loadWikiIndex();
    initWikiSearch();
});
