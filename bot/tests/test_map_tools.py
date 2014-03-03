import os
import unittest

from bot.libs.map_tools import MapParser, MapMath
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
        self.assertEqual(targets_by_distance[0][0], (105, 105))
        self.assertEqual(targets_by_distance[1][0], (94, 94))
        self.assertEqual(targets_by_distance[2][0], (100, 89))
        self.assertEqual(targets_by_distance[3][0], (100, 115))


def suite():
    suite = unittest.TestSuite(tests=(TestMapMath,
                                      TestMapParser))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=1).run(suite())