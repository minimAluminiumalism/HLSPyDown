from gevent import monkey
monkey.patch_all()
import gevent
import requests
import os
import sys
import time
import re
import json
import subprocess
from simple_progressbar import SimpleProgressBar
from urllib.parse import urljoin
from gevent.pool import Pool


class Downloader:
    def __init__(self, pool_size, cid, retry=5):
        self.pool = Pool(pool_size)
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.dir = ''
        self.ts_total = 0
        self.headers = {
        }
        self.succed = {}
        self.cid = cid
        self.ts_file_index = 0
        self.pbar = SimpleProgressBar(1, self.cid, self.ts_file_index, self.ts_total).update_received(0)
        self.failed_list = []

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def run(self, m3u8_url, cid, dir=''):
        self.dir = dir
        if self.dir and not os.path.isdir(self.dir):
            os.makedirs(self.dir)

        r = self.session.get(m3u8_url, timeout=10, headers=self.headers)
        if r.ok:
            body = r.content

            # Encrypted stream should use FFmpeg rather than traditional way to concat.
            if "EXT-X-KEY" in str(body, encoding="UTF-8"):
                hls_encrypted = True
                with open("{}.m3u8".format(self.cid), "w") as f:
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
                            print(self.cid)
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
                    key_response = requests.get(m3u8_key_url, headers=self.headers)
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
                    self.config_m3u8(same_perfix_mark)
                ts_list = list(zip(ts_list, [n for n in range(len(ts_list))]))
                if ts_list:
                    self.ts_total = len(ts_list)
                    self._download(ts_list)
                    self._join_file(hls_encrypted, cid)
                self.ts_file_index = 0
                self.ts_total = 0

        else:
            print(r.status_code, "m3u8 error.")
            # Handle "nonexistence m3u8 file" error, this error may hint that the movie is offline or unavailable.
            # New function required: put the cid of offline(unavailable) movie to a central online platform like Airtable(https://airtable.com/)
            if r.status_code == 404:
                with open("failed_list", "a") as f:
                    f.write(self.cid + "\n")
                    f.close()
            else:
                os._exit(0)

    def config_m3u8(self, same_perfix_mark):
        f = open('{}.m3u8'.format(self.cid), 'r+')
        flist = f.readlines()
        for i in range(0, len(flist)):
            if 'EXT-X-KEY' in flist[i]:
                patterns = re.compile('URI=\"(.*?)\"')
                raw_key_url = re.findall(patterns, flist[i])[0]
                flist[i] = flist[i].replace(raw_key_url, '{}.key'.format(self.cid))
            elif flist[i].startswith('https'):
                flist[i] = flist[i].split('/')[-1]
            i += 1
        f = open('{}.m3u8'.format(self.cid), 'w+')
        f.writelines(flist)

    def _download(self, ts_list):
        self.pool.map(self._worker, ts_list)

    def _worker(self, ts_tuple):
        url = ts_tuple[0]
        index = ts_tuple[1]
        ts_file_index = 0
        retry = self.retry
        while retry:
            try:
                r = self.session.get(url, timeout=50, headers=self.headers)
                # exception detection module, experimental!
                if r.status_code != 200:
                    print(r.status_code)
                    self.failed_list.append(url)
                file_name = url.split('/')[-1].split('?')[0]
                self.pbar = SimpleProgressBar(self.ts_total, self.cid, self.ts_file_index, self.ts_total).update_received(self.ts_file_index)
                self.ts_file_index += 1
                with open(os.path.join(self.dir, file_name), 'wb') as f:
                    f.write(r.content)
                    f.close()
                self.succed[index] = file_name
                return
            except Exception as e:
                print("\n", e)
                retry -= 1
        print(self.failed_list)
        return

    def _join_file(self, hls_encrypted, cid):
        if hls_encrypted:
            subprocess.call(
                [
                    'ffmpeg', '-protocol_whitelist',
                    "concat,file,subfile,http,https,tls,rtp,tcp,udp,crypto",
                    '-allowed_extensions', 'ALL', '-i', '{}.m3u8'.format(cid), '-c', 'copy',
                    '{}.mp4'.format(cid)
                ]
            )

            for root, dirs, files in os.walk(os.getcwd()):
                for name in files:
                    if name.endswith(".ts"):
                        os.remove(os.path.join(root, name))
            os.remove(os.path.join(self.dir, "{}.m3u8".format(cid)))
        else:
            index = 0
            outfile = ''
            while index < self.ts_total:
                file_name = self.succed.get(index, '')
                if file_name:
                    infile = open(os.path.join(self.dir, file_name), 'rb')
                    if not outfile:
                        outfile = open(os.path.join(self.dir, cid), 'wb')
                    outfile.write(infile.read())
                    infile.close()
                    os.remove(os.path.join(self.dir, file_name))
                    index += 1
                else:
                    time.sleep(1)
            if outfile:
                outfile.close()


if __name__ == '__main__':
    m3u8_url = sys.argv[1]
    cid = sys.argv[2]
    current_directory = os.getcwd()
    downloader = Downloader(100, cid)
    downloader.run(m3u8_url, cid, current_directory)
