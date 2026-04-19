from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as etree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from template_env import static_url

from .link_dictionary import (
    PreviewDictionary,
    PreviewEntry,
    href_keys,
    load_previews,
    norm_spaces,
    norm_term,
    visible_anchor_text,
)

TRANSPARENT_PIXEL = (
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
)


@dataclass(frozen=True)
class ResolvedPreview:
    title: str
    image: str | None
    image_width: int | None
    image_height: int | None
    synopsis: str


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


class LinkPreviewExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {
            "previews_path": [
                Path("wiki/_tech/link_previews.md"),
                "Path to link-preview dictionary",
            ],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown):
        previews_path = Path(self.getConfig("previews_path"))
        md.treeprocessors.register(
            LinkPreviewTreeprocessor(md, previews_path),
            "link_preview",
            11,
        )


class LinkPreviewTreeprocessor(Treeprocessor):
    def __init__(self, md: Markdown, previews_path: Path):
        super().__init__(md)
        self.previews_path = previews_path
        self.previews = PreviewDictionary(by_href={}, by_term={})
        self.href_preview_cache: dict[str, PreviewEntry | None] = {}

    def run(self, root: etree.Element):
        self.previews = load_previews(self.previews_path)
        self.href_preview_cache = {}
        if not self.previews.by_term and not self.previews.by_href:
            return root
        self._decorate_existing_links(root)
        return root

    def _decorate_existing_links(self, root: etree.Element):
        anchors = [element for element in root.iter() if _local_tag(element.tag) == "a"]

        for anchor in anchors:
            if any(
                "wiki-link-preview-card" in (child.get("class", ""))
                for child in list(anchor)
                if _local_tag(child.tag) == "span"
            ):
                continue

            href = anchor.get("href", "")
            if href.strip().startswith("#"):
                continue

            if len(anchor) == 0:
                text = norm_spaces(anchor.text or "")
            else:
                text = visible_anchor_text(anchor)
            is_autolink = anchor.get("data-wiki-autolink") == "1"
            preview = self._resolve_preview(
                href=href,
                text_key=text,
                fallback_title=text,
                is_autolink=is_autolink,
            )
            if preview is None:
                continue

            self._attach_preview(anchor, preview)

    def _resolve_preview(
        self,
        *,
        href: str,
        text_key: str,
        fallback_title: str,
        is_autolink: bool,
    ) -> ResolvedPreview | None:
        # Prefer term to avoid collisions when multiple terms share one href.
        term_preview = self.previews.by_term.get(norm_term(text_key))
        if term_preview is not None and term_preview.has_content:
            preview = term_preview
        elif is_autolink:
            # Auto-linked anchors should not take generic href fallback:
            # if term preview is removed, no card should be shown.
            return None
        else:
            preview = self._resolve_href_preview(href)
        if preview is None or not preview.has_content:
            return None

        title = preview.title or fallback_title
        if not title:
            title = norm_spaces(text_key)

        return ResolvedPreview(
            title=title,
            image=preview.image,
            image_width=preview.image_width,
            image_height=preview.image_height,
            synopsis=preview.synopsis,
        )

    def _attach_preview(self, anchor: etree.Element, preview: ResolvedPreview):
        classes = [cls for cls in anchor.get("class", "").split() if cls]
        if "wiki-link-preview-trigger" not in classes:
            classes.append("wiki-link-preview-trigger")
            anchor.set("class", " ".join(classes))

        card = etree.SubElement(anchor, "span")
        card_classes = ["wiki-link-preview-card"]
        if preview.image:
            card_classes.append("has-image")
        else:
            card_classes.append("no-image")
        card.set("class", " ".join(card_classes))
        card.set("aria-hidden", "true")

        style_parts: list[str] = []
        if preview.image_width is not None:
            style_parts.append(f"--wiki-preview-image-width: {preview.image_width}px")
        if preview.image_height is not None:
            style_parts.append(f"--wiki-preview-image-height: {preview.image_height}px")
        if style_parts:
            card.set("style", "; ".join(style_parts))

        row = etree.SubElement(card, "span")
        row.set("class", "wiki-link-preview-row")

        if preview.image:
            image = etree.SubElement(row, "img")
            image.set("class", "wiki-link-preview-image")
            if preview.image.startswith(("http://", "https://")):
                source = preview.image
            else:
                source = static_url(preview.image)
            image.set("src", TRANSPARENT_PIXEL)
            image.set("data-src", source)
            image.set("data-loaded", "0")
            image.set("alt", "")
            image.set("loading", "lazy")
            image.set("decoding", "async")
            if preview.image_width is not None:
                image.set("width", str(preview.image_width))
            if preview.image_height is not None:
                image.set("height", str(preview.image_height))

        content = etree.SubElement(row, "span")
        content.set("class", "wiki-link-preview-content")

        title = etree.SubElement(content, "span")
        title.set("class", "wiki-link-preview-title")
        title.text = preview.title

        if preview.synopsis:
            synopsis = etree.SubElement(content, "span")
            synopsis.set("class", "wiki-link-preview-synopsis")
            synopsis.text = preview.synopsis

    def _resolve_href_preview(self, href: str) -> PreviewEntry | None:
        cached = self.href_preview_cache.get(href)
        if href in self.href_preview_cache:
            return cached

        resolved: PreviewEntry | None = None
        for key in href_keys(href):
            resolved = self.previews.by_href.get(key)
            if resolved is not None:
                break

        self.href_preview_cache[href] = resolved
        return resolved
