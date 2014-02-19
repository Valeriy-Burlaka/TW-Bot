import os
import unittest
from unittest import mock

from bot.libs.map_tools import MapStorage, MapParser, MapMath, LocalStorage
from bot.tests.factories import TargetVillageFactory
from bot.tests.helpers import MapStorageHelper
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

    def test_get_targets_in_radius(self):
        source_coords = (100, 100)
        radius = 10
        dummy_targets = {(95, 95): [], (100, 115): [], (105, 105): [],
                         (100, 89): []}
        targets_in_radius = MapMath.get_targets_in_radius(source_coords, radius,
                                                          dummy_targets)
        self.assertEqual(len(targets_in_radius), 2)
        target_coords = [target[0] for target in targets_in_radius]
        self.assertIn((95, 95), target_coords)
        self.assertIn((105, 105), target_coords)


class TestMapStorage(unittest.TestCase):

    def setUp(self):
        self.helper = MapStorageHelper()
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


    # def save_villages(self, villages):
    #     f = shelve.open(self.mapfile)
    #     if 'villages' in f:
    #         temp_villages = f['villages']
    #     else:
    #         temp_villages = {}
    #     for villa in villages:
    #         temp_villages[villa.coords] = villa
    #     f['villages'] = temp_villages
    #     f.close()
    #
    #
    # def test_update_villages(self):
    #     valid_copies = {}
    #     for villa in self.valid_villages:
    #         coords = villa.coords
    #         valid_copies[coords] = villa
    #         valid_copies[coords].mine_levels = (1, 1, 1)
    #         valid_copies[coords].remaining_capacity = 1000
    #     self.map.update_villages(valid_copies)
    #     f = shelve.open(self.mapfile)
    #     for coords, villa in valid_copies.items():
    #         self.assertTrue(coords in f['villages'])
    #         self.assertEqual(villa.mine_levels, f['villages'][coords].mine_levels)
    #         self.assertEqual(villa.remaining_capacity, f['villages'][coords].remaining_capacity)
    #         self.assertTrue(coords in self.map.villages)
    #         self.assertEqual(villa.mine_levels, self.map.villages[coords].mine_levels)
    #         self.assertEqual(villa.remaining_capacity, self.map.villages[coords].remaining_capacity)
    #     f.close()

def suite():
    suite = unittest.TestSuite(tests=(TestMapMath,
                                      TestMapParser,
                                      TestMapStorage))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=1).run(suite())