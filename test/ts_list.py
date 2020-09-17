import requests
import json
import os
import re
import time
from urllib.parse import urljoin


headers = {
    "User-Agent": json.load(open("../header_config.json", "r")).get("headers"),
    "Cookie": json.load(open("../header_config.json", "r")).get("Cookie")
}


def list_generator():
    m3u8_url = 'https://str.dmm.com:443/digital/st1:4GpwPKLEm5TaSM862XOYYHo%2BDK-FwknGdGorie8w4FuS8jzDaebQYo6ywQHhpD%2Bt4Pf2aXzPsxZGnkYDRx3qWQ%3D%3D/2DewOm34U7r0QjaHdh8EFlu/-/chunklist_b3000000.m3u8?ld=geSOPvwNGtoSkwHpvxWwgt9qYQnea7Tt9Co1KLMzANcEnF838bVVtO4oZdeLNd4OmK%2B5xQwSo3hxhWfBQ4k6lalPrp7mU2C6DLnchGeeUgsKu96s8hrNmyLrWzvw6LZjiIw08mCt9RgvJACAvHE8RA%3D%3D&luid=cojp'
    cid = 'h_067nass00171'
    r = requests.get(m3u8_url, headers=headers)
    if r.ok:
        body = r.content

        # Encrypted stream should use FFmpeg rather than traditional way to concat.
        if "EXT-X-KEY" in str(body, encoding="UTF-8"):
            hls_encrypted = True
            with open("{}.m3u8".format(cid), "w") as f:
                f.write(str(body, encoding="UTF-8"))
            f.close()
        else:
            hls_encrypted = False

        # Judge if ts file url have same perfix with m3u8 file.
        if str(body).count("https://", 0, len(body)) >= 10:
            # ts file url have same perfix with m3u8 file.
            same_perfix_mark = True
        # ts file have a different perfix with m3u8 file, then find the right base URL.
        else:
            same_perfix_mark = False
            ts_test_list = []
            for n in body.split(b'\n'):
                if n and not n.startswith(b"#"):
                    ts_test_list.append(n)
            ts_url_back = str(ts_test_list[0], encoding="utf-8")

            m3u8_url = requests.get(m3u8_url).url
            split_url = m3u8_url.split("/")
            base_url = split_url[0] + "//" + split_url[2]
            ts_url = urljoin(base_url, ts_url_back)
            response = requests.get(ts_url, stream=True)
            if response.status_code == 200:
                pass
            else:
                url_index = 3
                while response.status_code != 200:
                    if url_index < len(split_url):
                        base_url = base_url + "/" + split_url[url_index]
                        ts_url = urljoin(base_url, ts_url_back)
                        response = requests.get(ts_url, stream=True)
                        url_index += 1
                    else:
                        alarm_info = "[Error Info]ts URL not found, check it manually."
                        print("""\033[31m{}\033[0m""".format(alarm_info))
                        print(cid)
                        os._exit(0)

        if body:
            if same_perfix_mark:
                ts_list = [str(n, encoding="utf-8") for n in body.split(b'\n') if
                           n and not n.startswith(b"#")]
            else:
                ts_list = [urljoin(base_url, str(n, encoding="utf-8")) for n in body.split(b'\n') if
                           n and not n.startswith(b"#")]
            if hls_encrypted:
                m3u8_key_list = [urljoin("", str(n, encoding="utf-8")) for n in body.split(b'\n') if
                                 n and n.startswith(b"#")]
                for ele in m3u8_key_list:
                    if "EXT-X-KEY" in ele:
                        m3u8_key_line = ele
                patterns = re.compile("URI=\"(.*?)\"")
                m3u8_key_url = re.findall(patterns, m3u8_key_line)[0]
                if "https://" or "http://" not in m3u8_key_url:
                    if same_perfix_mark:
                        m3u8_key_url = urljoin(m3u8_url, m3u8_key_url)
                    else:
                        m3u8_key_url = urljoin(base_url, m3u8_key_url)
                key_response = requests.get(m3u8_key_url, headers=headers)
                if key_response.status_code == 200:
                    with open("{}.key".format(cid), "wb") as f:
                        f.write(key_response.content)
                        f.close()
                else:
                    if os.path.exists("{}.key".format(cid)):
                        pass
                    else:
                        print(key_response.status_code, " online key file error, and local key file does not exits.",
                              "\n", """\033[31m{}\033[0m""".format("exiting..."))
                        time.sleep(2)
                        os._exit(0)
                config_m3u8(same_perfix_mark)

            print(len(ts_list))


def config_m3u8(same_perfix_mark):
    cid = 'h_067nass00171'
    f = open('{}.m3u8'.format(cid), 'r+')
    flist = f.readlines()
    for i in range(0, len(flist)):
        if 'EXT-X-KEY' in flist[i]:
            patterns = re.compile('URI=\"(.*?)\"')
            raw_key_url = re.findall(patterns, flist[i])[0]
            flist[i] = flist[i].replace(raw_key_url, '{}.key'.format(cid))
        elif flist[i].startswith('https'):
            flist[i] = flist[i].split('/')[-1]
        i += 1
    f = open('{}.m3u8'.format(cid), 'w+')
    f.writelines(flist)


list_generator()
