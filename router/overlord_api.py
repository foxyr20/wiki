from fastapi import APIRouter, Request

from config import Constants

router = APIRouter()


@router.get("/ping")
async def ping_overlord():
    return {"ok": True}


@router.post("/notify")
async def notify_overlord(request: Request):
    await Constants.req_from_over()
    return {"ok": True}
