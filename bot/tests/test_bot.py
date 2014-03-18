import unittest
from unittest.mock import patch, call
from unittest.mock import Mock

import settings
from bot.tests.factories import PlayerVillageFactory
from bot.app.bot import Bot


class TestBot(unittest.TestCase):
    def setUp(self):
        @patch.object(Bot, 'setup_attack_helper')
        @patch.object(Bot, 'setup_report_manager')
        @patch.object(Bot, 'setup_attack_manager')
        @patch.object(Bot, 'setup_village_manager')
        @patch.object(Bot, 'setup_request_manager')
        def setup_bot(patched_rm, patched_vm, patched_am, pacthed_report, patched_ah):
            bot =  Bot()
            return bot
        settings.DEBUG = True
        self.bot = setup_bot()

    def tearDown(self):
        settings.DEBUG = False

    def test_get_map_data(self):
        self.bot._get_map_overview = Mock()
        # 1 case: ._get_map_data is called with empty list
        # of farming centers. expected: return value = empty dict,
        # map overview was not requested.
        map_data = self.bot._get_map_data([], map_depth=10)
        self.assertEqual(map_data, {})
        self.assertEqual(len(self.bot._get_map_overview.method_calls), 0)
        # 2 case: ._get_map_data is called with 2 farming
        # centers, that belong to the same sector & with map_depth=1
        # expected: ._get_map_overview method is called once (for 1st
        # farming center); no calls to MapMath.get_area_corners method;
        # return value = merged sectors data.
        with patch('bot.app.bot.MapMath', autospec=True) as map_math:
            distinct_1 = PlayerVillageFactory(village_id=1, coords=(1, 1), name="1")
            distinct_2 = PlayerVillageFactory(village_id=2, coords=(2, 2), name="2")
            distinct_centers = [distinct_1, distinct_2]
            # set return value for .collect_sectors_data of map_parser,
            # so both centers are in the same sector
            self.bot.map_parser = Mock()
            self.bot.map_parser.collect_sector_data.return_value = \
                [{(1, 1): ['1001'], (2, 2): ['1002'], (3, 3): ['1003']},
                 {(4, 4): ['1004'], (5, 5): ['1005']},
                 {(8, 8): ['1008'], (10, 10): ['1010'], (6, 6): ['1006']},
                 {(0, 0): ['10000'], (0, 1000): ['10001'], (1000, 0): ['10002'],
                  (1000, 1000): ['10003']}]
            expected_return_value = {(1, 1): ['1001'], (2, 2): ['1002'],
                                     (3, 3): ['1003'], (4, 4): ['1004'],
                                     (5, 5): ['1005'], (6, 6): ['1006'],
                                     (8, 8): ['1008'], (10, 10): ['1010'],
                                     (0, 0): ['10000'], (0, 1000): ['10001'],
                                     (1000, 0): ['10002'], (1000, 1000): ['10003']}

            map_data = self.bot._get_map_data(distinct_centers, map_depth=1)
            self.assertEqual(map_data, expected_return_value)
            calls = self.bot._get_map_overview.mock_calls
            self.assertEqual(len(calls), 1)
            # .get_map_overview() was called with x=1,y=1,id=1 (first farming center)
            self.assertIn(call(1, 1, 1), calls)
            # refresh calls to _get_map_overview
            self.bot._get_map_overview.mock_calls = []
            # 3 case: 2 farming centers (same sector), map_depth=2.
            # expected: _get_map_overview is called 5 times (center +
            # 4 area corners. return value = merged sectors data
            map_math.get_area_corners.return_value = [(0, 0), (0, 1000),
                                                      (1000, 0), (1000, 1000)]
            map_data = self.bot._get_map_data(distinct_centers, map_depth=2)
            self.assertEqual(map_data, expected_return_value)
            calls = self.bot._get_map_overview.mock_calls
            self.assertEqual(len(calls), 5)
            self.assertIn(call(1, 1, 1), calls)
            self.assertIn(call(10000, 0, 0), calls)
            self.assertIn(call(10001, 0, 1000), calls)
            self.assertIn(call(10002, 1000, 0), calls)
            self.assertIn(call(10003, 1000, 1000), calls)
            # refresh calls to _get_map_overview
            self.bot._get_map_overview.mock_calls = []
            # 4 case: 2 farming centers in distinct sectors, map_depth=2.
            # expected: _get_map_overview is called 10 times (each center &
            # 4 area corners for each center. return value = merged sectors data
            self.bot.map_parser.collect_sector_data.return_value = \
                [{(1, 1): ['1001'], (3, 3): ['1003'], (1000, 1000): ['10003']},
                 {(2, 2): ['1002'], (4, 4): ['1004'], (5, 5): ['1005']},
                 {(8, 8): ['1008'], (10, 10): ['1010'], (6, 6): ['1006']},
                 {(0, 0): ['10000'], (0, 1000): ['10001'], (1000, 0): ['10002']}]
            map_data = self.bot._get_map_data(distinct_centers, map_depth=2)
            self.assertEqual(map_data, expected_return_value)
            calls = self.bot._get_map_overview.mock_calls
            expected_calls = [call(1, 1, 1),
                              call(2, 2, 2),
                              call(10000, 0, 0),
                              call(10000, 0, 0),
                              call(10001, 0, 1000),
                              call(10001, 0, 1000),
                              call(10002, 1000, 0),
                              call(10002, 1000, 0),
                              call(10003, 1000, 1000),
                              call(10003, 1000, 1000)]
            self.assertCountEqual(expected_calls, calls)

    def test_merge_sectors_data(self):
        sectors_data_unique = [{(1, 1): 'test11', (2, 2): 'test22'},
                               {(3, 3): 'test33', (4, 4): 'test44'}]
        expected = {(1, 1): 'test11', (2, 2): 'test22',
                    (3, 3): 'test33', (4, 4): 'test44'}
        actual = self.bot._merge_sectors_data(sectors_data_unique)
        self.assertTrue(expected, actual)

        sectors_data_non_unique = [{(1, 1): 'test11', (2, 2): 'test22'},
                                   {(1, 1): 'test33', (4, 4): 'test44'}]
        expected = {(1, 1): 'test33', (2, 2): 'test22',  (4, 4): 'test44'}
        actual = self.bot._merge_sectors_data(sectors_data_non_unique)
        self.assertTrue(expected, actual)

    def test_filter_distinct_centers(self):
        """
        Possible situations:
        1) All farming centers lie in the same sector as
        current attacker: expected result = [] (empty list)
        2) All farming centers lie in different sectors
        from attacker: expected result = list with all centers,
        current attacker not in returned list
        3) Some farming centers do lie in the same sector as
        current attacker and some centers do not. expected
        return: list with centers that do not lie in attacker's
        sector, attacker is not in returned list.
        Expected returned type = list of tuples, where each tuple
        is (x, y) coordinates
        """
        current_attacker = (1, 1)
        attacker_a = PlayerVillageFactory(coords=(2, 2), village_id=2, name="a")
        attacker_b = PlayerVillageFactory(coords=(3, 3), village_id=3, name="b")
        attacker_c = PlayerVillageFactory(coords=(4, 4), village_id=4, name="c")
        attacker_d = PlayerVillageFactory(coords=(5, 5), village_id=5, name="d")
        centers = [attacker_a, attacker_b, attacker_c, attacker_d]
        # some non-centers point added for plausibility
        all_in_one_data = [{(1, 1): '', (2, 2): '', (3, 3): '', (4, 4): '', (5, 5): ''},
                           {(6, 6): '', (7, 7): ''}]
        distinct_centers = self.bot._filter_distinct_centers(
            current_attacker, centers, all_in_one_data)
        self.assertEqual(distinct_centers, [])

        all_in_separate = [{(1, 1): '', (10, 10): ''},
                           {(2, 2): '', (3, 3): ''},
                           {(4, 4): '', (8, 8): '', (10, 10): '', (5, 5): ''}]
        distinct_centers = self.bot._filter_distinct_centers(
            current_attacker, centers, all_in_separate)
        self.assertCountEqual(distinct_centers, centers)

        in_same_and_separate = [{(1, 1): '', (2, 2): '', (3, 3): ''},
                                {(4, 4): '', (7, 7): '', (9, 9): ''},
                                {(5, 5): '', (6, 6): ''}]
        distinct_centers = self.bot._filter_distinct_centers(
            current_attacker, centers, in_same_and_separate)
        self.assertCountEqual(distinct_centers, [attacker_c, attacker_d])
