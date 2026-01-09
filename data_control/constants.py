from pathlib import Path

import httpx

OVERLORD_SOCKET = Path("/run/spf/overlord.sock")


class Constants:
    _data: dict[str, str] = {}

    @classmethod
    async def req_from_over(cls) -> None:
        transport = httpx.AsyncHTTPTransport(uds=str(OVERLORD_SOCKET))

        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            resp = await client.get("http://overlord/config")
            resp.raise_for_status()
            cls._data = resp.json()

    @classmethod
    def get_all_const(cls) -> dict[str, str]:
        return cls._data
