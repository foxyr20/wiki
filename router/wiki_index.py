import json
from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

router = APIRouter()

BASE = Path("static/search")
INDEX = BASE / "wiki_index.json"
META = BASE / "wiki_index.meta.json"


@router.get("/wiki/search/index")
def get_search_index(request: Request):
    client_hash = request.headers.get("If-None-Match")

    meta = json.loads(META.read_text(encoding="utf-8"))
    etag = meta["hash"]

    if client_hash == etag:
        return Response(status_code=304)

    return JSONResponse(
        content=json.loads(INDEX.read_text(encoding="utf-8")),
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=3600",
        },
    )
