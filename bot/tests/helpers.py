import os
import shutil

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
