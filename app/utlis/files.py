import asyncio
import typing as t

import aiohttp


async def download_file(url: str, session: aiohttp.ClientSession) -> bytes:
    resp = await session.get(url)
    if resp.status == 200:
        return await resp.read()

    raise FileExistsError('Exception while downloading file from $s', url)


async def download_files(urls: t.List[str]) -> t.List[bytes]:
    async with aiohttp.ClientSession() as session:
        return [
            resp for resp in await asyncio.gather(
                *[download_file(url, session) for url in urls]
            )
        ]
