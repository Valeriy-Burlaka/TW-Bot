import shelve
import shutil
import sqlite3
import sys
import os


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
