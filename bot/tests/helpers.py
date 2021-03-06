import os
import shutil
from unittest import mock

import settings
from bot.libs.request_management import RequestManager


class StorageHelper:

    def __init__(self):
        self.storage_path = None

    def create_test_storage(self, sub_folder='test'):
        self.storage_path = os.path.join(settings.TEST_DATA_FOLDER, sub_folder)
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
        return self.storage_path

    def clean_test_storage(self):
        if os.path.isdir(self.storage_path):
            shutil.rmtree(self.storage_path)


class MockCollection:

    @staticmethod
    def get_mocked_lock():
        config = {'acquire.return_value': None, 'release.return_value': None}
        mocked_lock = mock.Mock(**config)
        return mocked_lock

    @staticmethod
    def get_mocked_request_manager():
        mocked_rm = mock.Mock(spec=RequestManager)
        return mocked_rm
