import contextlib
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from data_control import Constants, ENVs
from router.overlord_api import router as overlord_api_router
from router.wiki_render import router as wiki_router


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await Constants.req_from_over()
    await ENVs.req_from_over()

    try:
        yield

    finally:
        pass


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

if os.getenv("FASTAPISTATIC") == "1":
    app.mount(
        "/static",
        StaticFiles(directory="static"),
        name="static",
    )

app.include_router(overlord_api_router)
app.include_router(wiki_router)
