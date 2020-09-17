import asyncio
import aiohttp
from ts_list import list_generator
import json

headers = {
    "User-Agent": json.load(open("../header_config.json", "r")).get("headers"),
    "Cookie": json.load(open("../header_config.json", "r")).get("Cookie")
}

ts_list = list_generator()[:20]


async def downloader(url):
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            print(response.status)


async def main():
    tasks = []
    for url in ts_list:
        tasks.append(downloader(url))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
