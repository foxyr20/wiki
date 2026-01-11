document.addEventListener("DOMContentLoaded", () => {
    function decodeId(raw) {
        if (!raw) return "";

        try {
            return decodeURIComponent(raw);
        } catch {
            return raw;
        }
    }

    function scrollToAnchor(id, smooth = true) {
        const target = document.getElementById(id);
        if (!target) return;

        target.scrollIntoView({
            behavior: smooth ? "smooth" : "auto",
            block: "start"
        });

        highlightHeading(target);
    }

    function highlightHeading(el) {
        el.classList.remove("heading-flash");
        void el.offsetWidth;
        el.classList.add("heading-flash");
    }

    document.addEventListener("click", e => {
        const link = e.target.closest("a[href^='#']");
        if (!link) return;

        const raw = link.getAttribute("href");
        if (!raw || raw === "#") return;

        e.preventDefault();

        const id = decodeId(raw.slice(1));
        if (!id) return;

        history.pushState(null, "", `#${encodeURIComponent(id)}`);
        scrollToAnchor(id, true);
    });

    if (location.hash && location.hash !== "#") {
        const id = decodeId(location.hash.slice(1));

        requestAnimationFrame(() => {
            scrollToAnchor(id, false);
        });
    }
});
