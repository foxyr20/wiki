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

        const re = new RegExp(`(${w})`, "ig");
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

    const words = query
        .toLowerCase()
        .split(/\s+/)
        .filter(w => w.length >= 2);

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

function makeResultUrl(result) {
    const base = `/wiki/${result.page.path}`;
    const sections = result.page.sections || [];
    const idx = result.sectionIndex;

    if (result.section.kind === "heading") {
        return base + "#" + encodeURIComponent(makeAnchor(result.section.text));
    }

    for (let i = idx; i >= 0; i--) {
        if (sections[i].kind === "heading") {
            return base + "#" + encodeURIComponent(makeAnchor(sections[i].text));
        }
    }

    return base;
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

    const words = query
        .toLowerCase()
        .split(/\s+/)
        .filter(w => w.length >= 2);

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

        const url = makeResultUrl(r);

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
    await loadWikiIndex();
    initWikiSearch();
});
