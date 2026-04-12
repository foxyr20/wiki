function initWikiLinkPreview() {
    const triggers = Array.from(
        document.querySelectorAll(".content a.wiki-link-preview-trigger")
    );

    if (!triggers.length) return;

    function loadLinkPreviewMedia(link) {
        const images = link.querySelectorAll(".wiki-link-preview-image[data-src]");
        for (const image of images) {
            if (image.dataset.loaded === "1") continue;
            const src = image.dataset.src;
            if (!src) continue;
            image.src = src;
            image.dataset.loaded = "1";
            image.removeAttribute("data-src");
        }
    }

    let active = null;

    function closeActive() {
        if (!active) return;
        active.classList.remove("preview-open");
        active = null;
    }

    function closeAll() {
        closeActive();
        for (const link of triggers) {
            link.classList.remove("preview-open");
        }
    }

    function suppressHoverUntilInteraction() {
        document.body.classList.add("wiki-preview-suppress-hover");
        const clear = () => {
            document.body.classList.remove("wiki-preview-suppress-hover");
        };
        window.addEventListener("pointermove", clear, { once: true, passive: true });
        window.addEventListener("keydown", clear, { once: true });
    }

    // Defensive cleanup for BFCache/back navigation restore.
    function resetStateOnShow() {
        closeAll();
        const focused = document.activeElement;
        if (
            focused &&
            focused.classList &&
            focused.classList.contains("wiki-link-preview-trigger")
        ) {
            focused.blur();
        }
        suppressHoverUntilInteraction();
    }

    resetStateOnShow();
    window.addEventListener("pageshow", resetStateOnShow);

    for (const link of triggers) {
        link.addEventListener("mouseenter", () => {
            loadLinkPreviewMedia(link);
        });
        link.addEventListener("focusin", () => {
            loadLinkPreviewMedia(link);
        });
    }

    const isTouchLike = window.matchMedia("(hover: none), (pointer: coarse)").matches;
    if (!isTouchLike) return;

    for (const link of triggers) {
        link.addEventListener("click", (event) => {
            if (active === link) {
                return;
            }

            event.preventDefault();
            closeActive();
            loadLinkPreviewMedia(link);

            link.classList.add("preview-open");
            active = link;
        });
    }

    document.addEventListener("click", (event) => {
        if (!active) return;
        if (active.contains(event.target)) return;
        closeActive();
    });

    window.addEventListener("resize", closeActive);
    document.addEventListener("scroll", closeActive, { passive: true });
}

document.addEventListener("DOMContentLoaded", () => {
    initWikiLinkPreview();
});
