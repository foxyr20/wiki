from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from markdown import Markdown

from config import Constants
from template_env import templates

from .extensions import (
    AutoButtonsExtension,
    AutoLinkExtension,
    ButtonExtension,
    CardExtension,
    ColorExtension,
    ConstExtension,
    DialogExtension,
    FolderTreeExtension,
    FootnoteExtension,
    GridExtension,
    HierarchyExtension,
    ImageExtension,
    LinkPreviewExtension,
    RedactExtension,
    RegistryExtension,
    RestrictedExtension,
    SmallTextExtension,
    StrikethroughExtension,
    StripCommentsExtension,
    TemplateIncludeExtension,
    TocTreeExtension,
    WikiMetaExtension,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
WIKI_DIR = BASE_DIR / "wiki"


@router.get("/wiki/{page:path}", response_class=HTMLResponse)
def wiki_page(request: Request, page: Path):
    md_path = WIKI_DIR / page
    if md_path.is_dir() or str(page).endswith("/"):
        md_path = md_path / "index.md"
    else:
        md_path = md_path.with_suffix(".md")

    if not md_path.resolve().is_relative_to(WIKI_DIR.resolve()):
        return Response(
            content="Invalid path",
            status_code=403,
            media_type="text/html",
        )

    try:
        content = md_path.read_text(encoding="utf-8")

    except FileNotFoundError:
        return Response(
            content="Page not found",
            status_code=404,
            media_type="text/html",
        )

    md = Markdown(
        extensions=[
            # ---
            "fenced_code",  # Блоки кода через тройные кавычки (```), как на GitHub
            "tables",  # Markdown-таблицы
            "smarty",  # Типографические ковычки
            "nl2br",  # Превращает одиночные \n в <br />
            "tables",  # Markdown-таблицы
            "footnotes",  # Кривые сноски
            # ---
            TocTreeExtension(),  # Автоматическое оглавление по заголовкам
            ConstExtension(constants=Constants.get_all_const()),  # Константы для замены
            StripCommentsExtension(),  # Очистка комментариев
            FolderTreeExtension(),  # Красивое оформление путей и папок
            HierarchyExtension(
                branch_threshold=3,
                max_chain_length=4,
            ),  # Адаптивные иерархические схемы: цепочки и ветки
            TemplateIncludeExtension(),  # Вставка однотипных блоков из wiki/_tech/template
            DialogExtension(),  # Обработка диалогов
            RedactExtension(),  # Позволяет динамически отредачить и засекретить информацию
            RegistryExtension(),  # Расширение для особых типов таблиц
            CardExtension(),  # Позволяет билдить карточки
            ColorExtension(),  # Красить текст в разный цвет
            SmallTextExtension(),  # Маленький текст
            StrikethroughExtension(),  # Зачёрктуный текст
            ButtonExtension(),  # Кнопочки
            AutoButtonsExtension(wiki_dir=WIKI_DIR),  # Автоматические кнопочки
            GridExtension(),  # Грид лейаут
            ImageExtension(),  # Картиночки
            RestrictedExtension(),  # Запрещённая информация
            AutoLinkExtension(autolinks_path=WIKI_DIR / "_tech" / "autolinks.md"),
            LinkPreviewExtension(previews_path=WIKI_DIR / "_tech" / "link_previews.md"),
            FootnoteExtension(),  # Менее кривые сноски
            WikiMetaExtension(),  # Заголовки-мета в начале файла (например, автор, дата)
        ],
    )

    setattr(md, "current_file", md_path)
    rendered_html = md.convert(content)
    meta: dict[str, str] = getattr(md, "wiki_meta", {})

    title = meta.get("title", "ЗАБЫЛИ НАИМЕНОВАНИЕ УСТАНОВИТЬ")
    date = meta.get("date")

    author: list[str] | None = None
    author_raw = meta.get("author")
    if author_raw:
        author = [a.strip() for a in author_raw.split(",") if a.strip()]

    background_url = meta.get("background")

    return templates.TemplateResponse(
        request,
        "wiki_template.html",
        {
            "content": rendered_html,
            "title": title,
            "date": date,
            "author": author,
            "background_url": background_url,
        },
    )
