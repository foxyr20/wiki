from pathlib import Path
from typing import Any

import httpx

OVERLORD_SOCKET = Path("/run/spf/overlord.sock")


async def _fetch_json(url: str) -> dict[str, Any]:
    transport = httpx.AsyncHTTPTransport(uds=str(OVERLORD_SOCKET))

    async with httpx.AsyncClient(
        transport=transport,
        timeout=5.0,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


class Constants:
    _data: dict[str, str] = {}

    @classmethod
    async def req_from_over(cls) -> None:
        cls._data = await _fetch_json("http://overlord/config")

    @classmethod
    def get_all_const(cls) -> dict[str, str]:
        return cls._data


class ENVs:
    _data: dict[str, str] = {}

    @classmethod
    async def req_from_over(cls) -> None:
        cls._data = await _fetch_json("http://overlord/env")

    @classmethod
    def get(cls, key: str, default: Any) -> Any:
        return cls._data.get(key, default)
