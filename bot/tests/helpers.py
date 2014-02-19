import os
import shutil
from unittest import mock

import settings


class MapStorageHelper:

    def __init__(self):
        self.storage_path = None

    def create_test_storage(self, sub_folder='test'):
        self.storage_path = os.path.join(settings.MAP_DATA_FOLDER, sub_folder)
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
        return self.storage_path

    def clean_test_storage(self):
        if os.path.isdir(self.storage_path):
            shutil.rmtree(self.storage_path)


class MockCollection:

    @staticmethod
    def get_patched_lock():
        config = {'acquire.return_value': None, 'release.return_value': None}
        patched_lock = mock.Mock(**config)
        return patched_lock

    @staticmethod
    def get_patched_request_manager():
        patcher = mock.patch('bot.libs.request_management.RequestManager',
                             autospec=True)
        patched_rm = patcher.start()
        return patched_rm
