import requests
import os
from urllib.parse import urljoin

m3u8_url = input("m3u8 URL: ")

ts_back_url = "000.ts"

split_url = m3u8_url.split("/")
base_url = split_url[0] + "//" + split_url[2]
ts_url = urljoin(base_url, ts_back_url)

response = requests.get(ts_url, stream=True)
if response.status_code == 200:
    ts_url = ts_url
else:
    url_index = 3
    while response.status_code != 200:
        if url_index <= len(split_url):
            base_url = base_url + "/" + split_url[url_index]
            ts_url = urljoin(base_url, ts_back_url)
            response = requests.get(ts_url, stream=True)
            #print(ts_url, response.status_code)
            url_index += 1
        else:
            alarm_info = "ts URL not found, check it manually."
            print("""\033[31m{}\033[0m""".format(alarm_info))
            os._exit(0)