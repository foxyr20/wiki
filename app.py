import contextlib
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import Constants
from router.overlord_api import router as overlord_api_router
from router.wiki_index import router as wiki_index_router
from router.wiki_render import router as wiki_render_router
from scripts.index_wiki import build_index, is_index_stale

LOCAL_RUN = os.getenv("FASTAPISTATIC") == "1"


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    if not LOCAL_RUN:
        await Constants.req_from_over()

    if is_index_stale():
        build_index()

    yield


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

if LOCAL_RUN:
    app.mount(
        "/static",
        StaticFiles(directory="static"),
        name="static",
    )

app.include_router(overlord_api_router)
app.include_router(wiki_index_router)
app.include_router(wiki_render_router)
