from gevent import monkey
monkey.patch_all()
import gevent
import requests
import os
import sys
import time
import subprocess
from progressbar import *
from urllib.parse import urljoin
from gevent.pool import Pool


class Downloader:
    def __init__(self, pool_size, retry=3):
        self.pool = Pool(pool_size)
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.dir = ''
        self.succed = {}
        self.failed = []
        self.ts_total = 0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36"
        }
        self.ts_file_index = 0
        self.widgets = ['Progress: ', Percentage(), ' ', Bar('#'), ' ', Timer(), ' ', ETA(), ' ', FileTransferSpeed()]
        self.pbar = ProgressBar(widgets=self.widgets, maxval=10*self.ts_total).start()

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def run(self, m3u8_url, dir=''):
        self.dir = dir
        if self.dir and not os.path.isdir(self.dir):
            os.makedirs(self.dir)

        r = self.session.get(m3u8_url, timeout=10, headers=self.headers)
        if r.ok:
            body = r.content

            # Encrypted stream should use FFmpeg rather than traditional way to concat.
            if "EXT-X-KEY" in str(body, encoding="UTF-8"):
                hls_encrypted = True
                with open("index.m3u8", "w") as f:
                    f.write(str(body, encoding="UTF-8"))
                f.close()
            else:
                hls_encrypted = False

            # Find the right base URL
            ts_test_list = []
            for n in body.split(b'\n'):
                if n and not n.startswith(b"#"):
                    ts_test_list.append(n)
            ts_url_back = str(ts_test_list[0], encoding="utf-8")

            split_url = m3u8_url.split("/")
            base_url = split_url[0] + "//" + split_url[2]
            ts_url = urljoin(base_url, ts_url_back)
            response = requests.get(ts_url, stream=True)
            if response.status_code == 200:
                pass
            else:
                url_index = 3
                while response.status_code != 200:
                    if url_index <= len(split_url):
                        base_url = base_url + "/" + split_url[url_index]
                        ts_url = urljoin(base_url, ts_url_back)
                        response = requests.get(ts_url, stream=True)
                        url_index += 1
                    else:
                        alarm_info = "[Error Info]ts URL not found, check it manually."
                        print("""\033[31m{}\033[0m""".format(alarm_info))
                        os._exit(0)

            if body:
                ts_list = [urljoin(base_url, str(n, encoding="utf-8")) for n in body.split(b'\n') if
                           n and not n.startswith(b"#")]
                ts_list = list(zip(ts_list, [n for n in range(len(ts_list))]))
                if ts_list:
                    self.ts_total = len(ts_list)
                    # print(self.ts_total)
                    self.pbar = ProgressBar(widgets=self.widgets, maxval=self.ts_total).start()
                    self._download(ts_list)
                    g1 = gevent.spawn(self._join_file, hls_encrypted)
                    g1.join()

        else:
            print(r.status_code)
            os._exit(0)

    def _download(self, ts_list):
        self.pool.map(self._worker, ts_list)
        if self.failed:
            ts_list = self.failed
            self.failed = []
            self._download(ts_list)
        self.pbar.start().finish()

    def _worker(self, ts_tuple):
        url = ts_tuple[0]
        index = ts_tuple[1]
        # base_url = ts_tuple[2]
        ts_file_index = 0
        retry = self.retry
        while retry:
            #try:
            r = self.session.get(url, timeout=20)
            if r.ok:
                file_name = url.split('/')[-1].split('?')[0]
                self.pbar.update(self.ts_file_index*10+1)
                self.ts_file_index += 1
                with open(os.path.join(self.dir, file_name), 'wb') as f:
                    f.write(r.content)
                self.succed[index] = file_name
                return
            #except:
                #retry -= 1
        print('[FAILED]%s' % url)
        self.failed.append((url, index))

    def _join_file(self, hls_encrypted):
        if hls_encrypted:
            if sys.argv[2].endswith(".mp4"):
                video_name = sys.argv[2].replace(".mp4", "")
            else:
                video_name = sys.argv[2]

            subprocess.call(
                [
                    'ffmpeg', '-protocol_whitelist',
                    "concat,file,subfile,http,https,tls,rtp,tcp,udp,crypto",
                    '-allowed_extensions', 'ALL', '-i', 'index.m3u8', '-c', 'copy',
                    '{}.mp4'.format(video_name)
                ]
            )

            for root, dirs, files in os.walk(os.getcwd()):
                for name in files:
                    if name.endswith(".ts"):
                        os.remove(os.path.join(root, name))
            os.remove(os.path.join(self.dir, "index.m3u8"))
        else:
            index = 0
            outfile = ''
            while index < self.ts_total:
                file_name = self.succed.get(index, '')
                if file_name:
                    infile = open(os.path.join(self.dir, file_name), 'rb')
                    if not outfile:
                        outfile = open(os.path.join(self.dir, sys.argv[2]), 'wb')
                    outfile.write(infile.read())
                    infile.close()
                    os.remove(os.path.join(self.dir, file_name))
                    index += 1
                else:
                    time.sleep(1)
            if outfile:
                outfile.close()


if __name__ == '__main__':
    downloader = Downloader(20)
    current_directory = os.getcwd()
    downloader.run(sys.argv[1], current_directory)
