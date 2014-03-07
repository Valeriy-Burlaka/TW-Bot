import unittest
from unittest import mock
import os
import shelve

from bot.libs.common_tools import LocalStorage, Storage
from bot.tests.helpers import StorageHelper
from bot.tests.factories import TargetVillageFactory


class TestStorage(unittest.TestCase):

    def setUp(self):
        self.helper = StorageHelper()
        self.storage_folder = self.helper.create_test_storage()
        self.storage_name = os.path.join(self.storage_folder, 'test_storage')

    def tearDown(self):
        self.helper.clean_test_storage()

    def test_init_with_local_processor(self):
        map_storage = Storage(storage_type='local_file',
                                 storage_name=self.storage_name)
        self.assertIsInstance(map_storage.storage_processor, LocalStorage)

    def test_init_with_non_existing_processor(self):
        self.assertRaises(NotImplementedError, Storage, 'not_implemented', 'test')

    @mock.patch('bot.libs.common_tools.LocalStorage', autospec=True)
    def test_retrieve_from_local_delegated_to_processor(self, mocked_storage):
        map_storage = Storage(storage_type='local_file',
                                 storage_name=self.storage_name)
        processor = map_storage.storage_processor
        map_storage.get_saved_villages()
        processor.get_saved_villages.assert_called_once_with()

    @mock.patch('bot.libs.common_tools.LocalStorage', autospec=True)
    def test_save_to_local_delegated_to_processor(self, mocked_storage):
        map_storage = Storage(storage_type='local_file',
                                 storage_name=self.storage_name)
        processor = map_storage.storage_processor
        villages = {(0, 0): []}
        map_storage.update_villages(villages)
        processor.update_villages.assert_called_once_with(villages)


class TestLocalStorage(unittest.TestCase):

    def setUp(self):
        self.helper = StorageHelper()
        self.storage_folder = self.helper.create_test_storage()
        self.storage_name = os.path.join(self.storage_folder, 'test_storage')

    def tearDown(self):
        self.helper.clean_test_storage()

    def test_get_saved_villages(self):
        storage = LocalStorage(self.storage_name)
        villages = storage.get_saved_villages()
        self.assertIsInstance(villages, dict)
        self.assertEqual(len(villages), 0)

        test_village = TargetVillageFactory()
        save_data = {}
        save_data[test_village.coords] = test_village
        manual_storage = shelve.open(self.storage_name)
        manual_storage['villages'] = save_data
        manual_storage.close()
        villages = storage.get_saved_villages()
        self.assertIsInstance(villages, dict)
        self.assertEqual(len(villages), 1)
        self.assertIn(test_village.coords, villages)
        self.assertEqual(test_village.id, villages[test_village.coords].id)

    def test_update_villages(self):
        storage = LocalStorage(self.storage_name)
        test_villages = TargetVillageFactory.build_batch(5)

        save_data = {village.coords: village for village in test_villages}
        storage.update_villages(save_data)
        manual_storage = shelve.open(self.storage_name)
        self.assertIn('villages', manual_storage)
        self.assertCountEqual(manual_storage['villages'], save_data)
        manual_storage.close()

        for village in test_villages:
            village.mine_levels = (10, 10, 10)
            village.remaining_capacity = 10000
            village.last_visited = 100000
            village.defended = True
        save_data = {village.coords: village for village in test_villages}
        storage.update_villages(save_data)
        manual_storage = shelve.open(self.storage_name)

        self.assertIn('villages', manual_storage)
        for village in test_villages:
            saved_village = manual_storage['villages'][village.coords]
            self.assertEqual(village.coords, saved_village.coords)
            self.assertEqual(village.id, saved_village.id)
            self.assertEqual(village.mine_levels, saved_village.mine_levels)
            self.assertEqual(village.population, saved_village.population)
            self.assertEqual(village.remaining_capacity, saved_village.remaining_capacity)
            self.assertEqual(village.last_visited, saved_village.last_visited)
            self.assertEqual(village.defended, saved_village.defended)
        manual_storage.close()

    def test_save_attacks(self):
        storage = LocalStorage(self.storage_name)
        save_data_arrivals = {(1, 1): 1000, (2, 2): 2000, (3, 3): 3000}
        save_data_returns = {1: [1000, 2000, 3000], 2: [1000, 2000, 3000]}

        storage.save_attacks(arrivals=save_data_arrivals,
                             returns=save_data_returns)
        manual_storage = shelve.open(self.storage_name)
        self.assertIn('arrivals', manual_storage)
        self.assertEqual(manual_storage['arrivals'], save_data_arrivals)
        self.assertIn('returns', manual_storage)
        self.assertEqual(manual_storage['returns'], save_data_returns)

