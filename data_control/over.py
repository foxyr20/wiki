import logging
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

OVERLORD_SOCKET = Path("/run/spf/overlord.sock")


async def _fetch_json(url: str) -> dict[str, Any]:
    transport = httpx.AsyncHTTPTransport(uds=str(OVERLORD_SOCKET))

    try:
        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            log.warning(
                "Overlord returned %s for %s",
                resp.status_code,
                url,
            )
            return {}

        return resp.json()

    except httpx.ConnectError:
        log.warning("Overlord socket not available: %s", OVERLORD_SOCKET)
        return {}

    except httpx.TimeoutException:
        log.warning("Overlord request timeout: %s", url)
        return {}

    except Exception as exc:
        log.exception("Unexpected error while fetching %s: %s", url, exc)
        return {}


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
