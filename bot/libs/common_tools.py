import shelve
import shutil
import sqlite3
import sys
import os
import re
import time
import base64
from urllib.request import urlopen, Request
from urllib.parse import urlencode

import requests


class Storage:
    """
    Delegates save & update operations to one of storage-helpers
    """

    def __init__(self, storage_type, storage_name):
        if storage_type == 'local_file':
            self.storage_processor = LocalStorage(storage_name)
        else:
            raise NotImplementedError("Specified storage type for map data"
                                      "is not implemented yet!")

    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            if not hasattr(self.storage_processor, name):
                raise NotImplementedError
            else:
                return getattr(self.storage_processor, name)(*args, **kwargs)
        return wrapper


class LocalStorage:
    """
    Handles retrieval & update of data saved in a local file.

    Methods:

    get_saved_villages:
        returns villages that were saved in a local shelve file
    update_villages(villages):
        updates information about (attacked) villages in a local
        shelve file
    save_attacks(arrivals, returns):
        saves given arrivals & returns in a local shelve file
    get_saved_arrivals:
        returns arrivals that were saved in a local shelve file
    get_saved_returns:
        returns 'returns', ye.
    """

    def __init__(self, storage_name):
        self.storage_name = storage_name

    def get_saved_villages(self):
        storage = shelve.open(self.storage_name)
        saved_villages = storage.get('villages', {})
        storage.close()
        return saved_villages

    def update_villages(self, villages):
        storage = shelve.open(self.storage_name)
        saved_villages = storage.get('villages', {})
        saved_villages.update(villages)

        storage['villages'] = saved_villages
        storage.close()

    def save_attacks(self, arrivals=None, returns=None):
        storage = shelve.open(self.storage_name)
        if arrivals:
            storage['arrivals'] = arrivals
        if returns:
            storage['returns'] = returns
        storage.close()

    def get_saved_arrivals(self):
        storage = shelve.open(self.storage_name)
        arrivals = storage.get('arrivals', {})
        storage.close()
        return arrivals

    def get_saved_returns(self):
        storage = shelve.open(self.storage_name)
        returns = storage.get('returns', {})
        storage.close()
        return returns


class CookiesExtractor:

    def get_initial_cookies(self, run_path, browser_name, host, names):
        cookies_filepath = self._get_cookies_filepath(browser_name)
        if not cookies_filepath:
            raise NotImplementedError("Sorry, seems that dumb bot doesn't"
                                      "now how to extract cookies from your"
                                      "browser!")
        new_path = self._copy_cookies_file(run_path, cookies_filepath)
        cookies = self._extract_cookies(browser_name, new_path, host, names)
        os.remove(new_path)
        return cookies

    @staticmethod
    def _get_cookies_filepath(browser_name):
        filepath = ''
        platform = sys.platform
        username = os.getlogin()
        if platform == 'linux':
            if browser_name.lower() in ['chrome', 'chromium']:
                filepath = "/home/{user}/.config/{browser}/Default/Cookies"
                filepath = filepath.format(user=username,
                                           browser=browser_name.lower())
        elif platform == 'win32':
            if browser_name.lower() == 'chrome':
                filepath = r'C:\Users\{user}\AppData\Local\Google\{browser}' \
                           r'\User Data\Default\Cookies'
                filepath = filepath.format(user=username,
                                           browser=browser_name.lower().capitalize())
        return filepath

    @staticmethod
    def _copy_cookies_file(run_path, cookies_path):
        new_path = os.path.join(run_path, 'cookies')
        shutil.copyfile(cookies_path, new_path)
        return new_path

    @staticmethod
    def _extract_cookies(browser_name, db_path, host, names, timeout=30):
        """
        Open given sqlite file and extracts cookies that belong to host.
        Returns list of tuples [(host, cookie, value), ...]
        """
        connection = sqlite3.connect(db_path, timeout=timeout)
        cursor = connection.cursor()
        if browser_name in ['chrome', 'chromium']:
            query = "select name, value from cookies where host_key=?"
        elif browser_name == 'mozilla':
            query = "select name, value from moz_cookies where host=?"
        cursor.execute(query, (host,))
        cookies_data = cursor.fetchall()
        cursor.close()
        connection.close()

        cookies_data = {cook[0]: cook[1] for cook in cookies_data if cook[0] in names}
        return cookies_data


class AutoLogin:

    def __init__(self, host, username, password):
        self.host = host
        self.global_host = self._get_global_hostname()
        self.username = username
        self.password = password

    def login_to_server(self):
        post_data = self._get_server_selection_data()
        response = self._show_server_selection(post_data)
        encrypt_pass = self._get_enc_password(response.text)
        post_data = {'user': self.username, 'password': encrypt_pass}
        server = 'server_' + self.host.split('.')[0]
        response = self._post_login_data(post_data, server)
        new_cookies = response.history[1].cookies.get_dict()
        return new_cookies

    def _get_server_selection_data(self):
        selection_data = {'user': self.username, 'password': self.password,
                          'cookie': 'false', 'clear': 'true'}
        return selection_data

    def _show_server_selection(self, post_data):
        """
        POSTs server selection request. Response contains encrypted
        user password for further POST.
        """
        url = 'http://{host}/index.php?action=login&' \
              'show_server_selection=1'.format(host=self.global_host)
        headers = self._get_login_headers()
        response = requests.post(url, headers=headers, data=post_data)
        return response

    @staticmethod
    def _get_enc_password(selection_data):
        """
        Parses response received after 'show_server_selection' request.
        Returns encrypted user password.
        """
        pswd_ptrn = re.compile(r'password[\W\w]+?value\W\W"([\W\w]+?)\W"')
        match = re.search(pswd_ptrn, selection_data)
        return match.group(1)

    def _post_login_data(self, post_data, server):
        url = 'http://{host}/index.php?action=login&' \
              '{server}'.format(host=self.global_host, server=server)
        headers = self._get_login_headers()
        response = requests.post(url, headers=headers, data=post_data)
        return response

    def _get_login_headers(self):
        headers = {}
        headers['host'] = self.host
        headers['connection'] = 'keep-alive'
        headers['accept'] = 'application/json, text/javascript, */*; q=0.01'
        headers['user-agent'] = 'Mozilla/5.0 (Windows NT 6.1; WOW64) ' \
                                'AppleWebKit/537.36 (KHTML, like Gecko) ' \
                                'Chrome/30.0.1599.101 Safari/537.36'
        headers['origin'] = 'http://{host}'.format(host=self.host)
        headers['x-requested-with'] = 'XMLHttpRequest'
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['accept-encoding'] = 'gzip,deflate,sdch'
        headers['referer'] = 'http://{host}'.format(host=self.host)

        return headers

    def _get_global_hostname(self):
        host = self.host.split('.')
        host[0] = 'www'
        host = '.'.join(host)
        return host


class AntigateWrapper:

    def __init__(self, key):
        self.key = key

    def get_captcha_answer(self, img_bytes):
        b64_img = base64.b64encode(img_bytes)
        req_data = {'method': 'base64',
                    'key': self.key,
                    'body': b64_img,
                    'numeric': '1', 'min_len': '6', 'max_len': '6'}
        req_data = urlencode(req_data).encode()
        req = Request('http://antigate.com/in.php', data=req_data)
        response = urlopen(req)
        # response.read() = b'OK|captcha_ID'
        resp_data = response.read().decode()
        if resp_data == 'ERROR_NO_SLOT_AVAILABLE':
            time.sleep(10)
            return self.get_captcha_answer(img_bytes)
        elif resp_data.startswith("ERROR"):
            raise AttributeError(resp_data)

        captcha_id = resp_data.split('|')[1]
        captcha_url = 'http://antigate.com/res.php?key={api_key}&' \
                      'action=get&id={cap_id}'.format(api_key=self.key,
                                                      cap_id=captcha_id)
        captcha_text = ""
        # average time of handling CAPTCHA on AntiGate service
        time.sleep(10)
        while not captcha_text:
            get_text_req = Request(captcha_url)
            response = urlopen(get_text_req)
            captcha_status = response.read().decode()
            # It's not a typo (CAPCHA)
            if captcha_status == 'CAPCHA_NOT_READY':
                time.sleep(5)
                continue
            elif captcha_status.startswith('OK'):
                captcha_text = captcha_status.split('|')[1]
            elif captcha_status.startswith("ERROR"):
                raise AttributeError(captcha_status)

        return captcha_text