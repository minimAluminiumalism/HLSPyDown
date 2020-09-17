import asyncio
import aiohttp
import json

headers = {
    "User-Agent": json.load(open("../header_config.json", "r")).get("headers"),
    "Cookie": json.load(open("../header_config.json", "r")).get("Cookie")
}



