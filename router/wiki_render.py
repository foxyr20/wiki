from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from markdown import Markdown

from data_control.over import Constants
from template_env import templates

from .extensions import (
    AutoLinkButtonsExtension,
    ButtonExtension,
    ConstExtension,
    FolderTreeExtension,
    ImgBlockExtension,
    ImgExtension,
    ImgUrlExtension,
    LobotomyExtension,
    RedactExtension,
    SmallTextExtension,
    StrikethroughExtension,
    StripCommentsExtension,
    TableImgExtension,
    TocTreeExtension,
    WarnIncludeExtension,
    WikiLinkExtension,
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
            AutoLinkButtonsExtension(wiki_dir=WIKI_DIR),  # Динамические кнопки
            "fenced_code",  # Блоки кода через тройные кавычки (```), как на GitHub
            "tables",  # Markdown-таблицы
            TableImgExtension(),  # Поддержка картинок в таблицах
            "meta",  # Заголовки-мета в начале файла (например, автор, дата)
            TocTreeExtension(),  # Автоматическое оглавление по заголовкам
            "admonition",  # Поддержка блоков с предупреждениями, заметками и пр.
            "footnotes",  # Сноски
            "smarty",  # Типографические ковычки
            "nl2br",  # Превращает одиночные \n в <br />
            WikiLinkExtension(),  # Поддержка [[url|name]] для вики-стилей
            ConstExtension(constants=Constants.get_all_const()),  # Константы для замены
            ImgUrlExtension(),  # Для нормальной работы ссылок
            ImgBlockExtension(),  # Для блоков с картинками и текстом
            RedactExtension(),  # Для обфускации информации с сайта пока не заглянут в код
            ImgExtension(),  # Макрос для картинок
            ButtonExtension(),  # Работа с кнопками и их оформлением
            StripCommentsExtension(),  # В пизду комментарии, так же стрипает весь текст
            FolderTreeExtension(),  # Для создания красивых деревьев
            SmallTextExtension(),  # Маленький текст
            StrikethroughExtension(),  # Зачёркнутый текст
            LobotomyExtension(),  # Немного красоты в вики
            WarnIncludeExtension(),  # Подстановка теплейтов
        ],
    )

    setattr(md, "current_file", md_path)
    rendered_html = md.convert(content)
    meta = getattr(md, "Meta", {})

    title = meta.get("title", [None])[0] or "ЗАБЫЛИ НАИМЕНОВАНИЕ УСТАНОВИТЬ"
    data = meta.get("date", [None])[0] or "ЗАБЫЛИ ДАТУ УСТАНОВИТЬ"
    background_url = meta.get("background", [None])[0] or "images/wallpaper.jpeg"

    return templates.TemplateResponse(
        "wiki_template.html",
        {
            "request": request,
            "content": rendered_html,
            "title": title,
            "data": data,
            "background_url": background_url,
        },
    )
