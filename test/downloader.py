import asyncio
import aiohttp
from list import Downloader
import json

headers = {
    "User-Agent": json.load(open("../header_config.json", "r")).get("headers"),
    "Cookie": json.load(open("../header_config.json", "r")).get("Cookie")
}

ts_list = Downloader.run()

print(len(ts_list))

