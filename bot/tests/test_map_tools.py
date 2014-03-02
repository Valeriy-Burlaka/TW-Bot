import os
import shelve
import unittest
from unittest import mock

from bot.libs.map_tools import MapStorage, MapParser, MapMath, LocalStorage
from bot.tests.factories import TargetVillageFactory
from bot.tests.helpers import StorageHelper
import settings


class TestMapParser(unittest.TestCase):

    def setUp(self):
        self.parser = MapParser()
        self.overviews_folder = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                             'map_overviews')

    def test_get_map_data_against_all_test_data(self):
        for filename in os.listdir(self.overviews_folder):
            with open(os.path.join(self.overviews_folder, filename)) as f:
                map_data = f.read()
                sectors_data = self.parser.get_map_data(map_data)
                self.assertIsInstance(sectors_data, list)

    def test_collect_sector_data(self):
        filename = os.path.join(self.overviews_folder, 'map_overview_200_300.html')
        with open(filename) as f:
            map_data = f.read()
        sectors_data = self.parser.collect_sector_data(map_data)
        self.assertIsInstance(sectors_data, list)
        for sector in sectors_data:
            self.assertIsInstance(sector, dict)

        first_sector = sectors_data[0]
        self.assertIn((194, 295), first_sector)
        self.assertEqual(first_sector[(194, 295)][0], '155394')  # village id
        self.assertIn((207, 305), first_sector)
        self.assertEqual(first_sector[(207, 305)][0], '135534')

class TestMapMath(unittest.TestCase):

    def test_get_area_corners(self):
        # MIN_X_MIN_Y = (50, 75)
        # MIN_X_MAX_Y = (50, 200)
        # MAX_X_MIN_Y = (175, 50)
        # MAX_X_MAX_Y = (200, 150)
        sample = [(50, 75), (100, 50), (150, 50), (175, 50), (125, 100),
                  (50, 125), (75, 150), (200, 150), (175, 175), (50, 200),
                  (150, 200)]
        corners = MapMath.get_area_corners(sample)
        self.assertEqual(len(corners), 4)
        self.assertIn((50, 75), corners)
        self.assertIn((50, 200), corners)
        self.assertIn((175, 50), corners)
        self.assertIn((200, 150), corners)

    def test_calculate_distance(self):
        self.assertEqual(MapMath.calculate_distance((100, 100), (200, 150)), 111.8)

    def test_get_targets_by_distance(self):
        source_coords = (100, 100)
        target_coords = [(94, 94), (100, 115), (105, 105), (100, 89)]
        # [((x, y), distance_to_source), ...]
        targets_by_distance = MapMath.get_targets_by_distance(source_coords,
                                                              target_coords)
        self.assertEqual(len(targets_by_distance), 4)
        print(targets_by_distance)
        self.assertEqual(targets_by_distance[0][0], (105, 105))
        self.assertEqual(targets_by_distance[1][0], (94, 94))
        self.assertEqual(targets_by_distance[2][0], (100, 89))
        self.assertEqual(targets_by_distance[3][0], (100, 115))


class TestMapStorage(unittest.TestCase):

    def setUp(self):
        self.helper = StorageHelper()
        self.storage_folder = self.helper.create_test_storage()
        self.storage_name = os.path.join(self.storage_folder, 'test_storage')

    def tearDown(self):
        self.helper.clean_test_storage()

    def test_init_with_local_processor(self):
        map_storage = MapStorage(storage_type='local_file',
                                 storage_name=self.storage_name)
        self.assertIsInstance(map_storage.storage_processor, LocalStorage)

    def test_init_with_non_existing_processor(self):
        self.assertRaises(NotImplementedError, MapStorage, 'not_implemented', 'test')

    @mock.patch('bot.libs.map_tools.LocalStorage', autospec=True)
    def test_retrieve_from_local_delegated_to_processor(self, mocked_storage):
        map_storage = MapStorage(storage_type='local_file',
                                 storage_name=self.storage_name)
        processor = map_storage.storage_processor
        map_storage.get_saved_villages()
        processor.get_saved_villages.assert_called_once_with()

    @mock.patch('bot.libs.map_tools.LocalStorage', autospec=True)
    def test_save_to_local_delegated_to_processor(self, mocked_storage):
        map_storage = MapStorage(storage_type='local_file',
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


def suite():
    suite = unittest.TestSuite(tests=(TestMapMath,
                                      TestMapParser,
                                      TestMapStorage))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=1).run(suite())