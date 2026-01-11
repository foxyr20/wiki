document.addEventListener("DOMContentLoaded", () => {
    const aside = document.querySelector(".toc-panel");
    if (!aside) return;

    const mdToc = document.querySelector(".content .toc");
    if (!mdToc) {
        aside.classList.add("toc-empty");
        return;
    }

    const rootUl = mdToc.querySelector("ul");
    if (!rootUl) {
        mdToc.remove();
        aside.classList.add("toc-empty");
        return;
    }

    rootUl.classList.add("toc-inner");
    aside.appendChild(rootUl);
    mdToc.remove();

    function decodeHash(hash) {
        if (!hash || hash === "#") return "";

        try {
            return decodeURIComponent(hash.replace(/^#/, ""));
        } catch {
            return hash.replace(/^#/, "");
        }
    }

    function findLinkByHash(hash) {
        const want = decodeHash(hash);
        if (!want) return null;

        for (const a of rootUl.querySelectorAll("a[href^='#']")) {
            const href = a.getAttribute("href");
            if (!href) continue;

            if (decodeHash(href) === want) {
                return a;
            }
        }

        return null;
    }

    rootUl.querySelectorAll("li").forEach(li => {
        const childUl = li.querySelector(":scope > ul");
        const link = li.querySelector(":scope > a");

        if (!link) return;

        const row = document.createElement("div");
        row.className = "toc-row";

        row.appendChild(link);

        if (childUl) {
            childUl.classList.add("toc-collapsed");

            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "toc-toggle";
            btn.textContent = "▸";

            btn.addEventListener("click", e => {
                e.preventDefault();
                e.stopPropagation();

                const hidden = childUl.classList.toggle("toc-collapsed");
                btn.classList.toggle("is-open", !hidden);
            });

            row.appendChild(btn);
        }

        li.insertBefore(row, childUl || null);
    });

    function setActive(hash) {
        const link = findLinkByHash(hash);

        rootUl.querySelectorAll("a.is-active")
            .forEach(a => a.classList.remove("is-active"));

        if (!link) return;

        link.classList.add("is-active");

        let li = link.closest("li");
        while (li) {
            const parentUl = li.parentElement;

            if (
                parentUl &&
                parentUl !== rootUl &&
                parentUl.classList.contains("toc-collapsed")
            ) {
                parentUl.classList.remove("toc-collapsed");

                const parentLi = parentUl.closest("li");
                const btn = parentLi?.querySelector(":scope > .toc-row > .toc-toggle");
                if (btn) btn.classList.add("is-open");
            }

            li = li.parentElement.closest("li");
        }
    }

    rootUl.addEventListener("click", e => {
        const link = e.target.closest(".toc-row > a[href^='#']");
        if (!link) return;

        e.preventDefault();
        setActive(link.getAttribute("href"));
    });

    window.addEventListener("hashchange", () => {
        setActive(location.hash);
    });

    if (location.hash) {
        setActive(location.hash);
    }
});
