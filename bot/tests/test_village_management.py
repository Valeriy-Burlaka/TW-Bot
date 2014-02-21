import os
import unittest
from unittest.mock import call, patch

import settings
from bot.tests.helpers import MockCollection
from bot.libs.village_management import VillageManager, TargetVillage


class TestVillageManager(unittest.TestCase):

    def setUp(self):
        settings.DEBUG = True
        # Patch MapStorage class to avoid garbage-creation
        # (shelve file)
        with patch('bot.libs.village_management.MapStorage',
                        autospec=True) as patched_storage:
            # Patch MapParser to control return value of .collect_sectors_data
            # method in tests
            with patch('bot.libs.village_management.MapParser') as patched_parser:
                patched_storage.get_saved_villages.return_value = {}
                mocked_lock = MockCollection.get_mocked_lock()
                mocked_rm = self.get_mocked_request_manager()
                self.village_manager = VillageManager(mocked_rm, mocked_lock)

    def tearDown(self):
        settings.DEBUG = False

    def get_mocked_request_manager(self):
        mocked_rm = MockCollection.get_mocked_request_manager()
        config = {'get_map_overview.return_value': '',
                  'get_train_screen.return_value': '',
                  'get_overviews_screen.return_value': '',
                  'get_village_overview.return_value': ''}
        mocked_rm.configure_mock(**config)

        return mocked_rm

    def test_get_map_data(self):
        # refresh calls to request_manager:
        self.village_manager.request_manager.method_calls = []
        # 1 case: ._get_map_data is called with empty list
        # of farming centers. expected: return value = empty dict,
        # no calls to request_manager were performed
        map_data = self.village_manager._get_map_data([], map_depth=10)
        self.assertEqual(map_data, {})
        self.assertEqual(len(self.village_manager.request_manager.method_calls), 0)
        # 2 case: ._get_map_data is called with 2 farming
        # centers, that belong to the same sector & with map_depth=1
        # expected: ._get_map_overview method is called once (for 1st
        # farming center); no calls to MapMath.get_area_corners method;
        # return value = merged sectors data.
        with patch('bot.libs.village_management.MapMath', autospec=True) as map_math:
            distinct_centers = []
            distinct_centers.append(((1, 1), 1))  # ((x, y), id)
            distinct_centers.append(((2, 2), 2))
            # set return value for .collect_sectors_data of map_parser,
            # so both centers are in the same sector
            self.village_manager.map_parser.collect_sector_data.return_value = \
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
            map_data = self.village_manager._get_map_data(distinct_centers, map_depth=1)
            self.assertEqual(map_data, expected_return_value)
            calls_to_rm = self.village_manager.request_manager.method_calls
            self.assertEqual(len(calls_to_rm), 1)
            self.assertIn(call.get_map_overview(1, 1, 1), calls_to_rm)
            # refresh calls to request_manager:
            self.village_manager.request_manager.method_calls = []
            # 3 case: 2 farming centers (same sector), map_depth=2.
            # expected: _get_map_overview is called 5 times (center +
            # 4 area corners. return value = merged sectors data
            map_math.get_area_corners.return_value = [(0, 0), (0, 1000),
                                                      (1000, 0), (1000, 1000)]
            map_data = self.village_manager._get_map_data(distinct_centers, map_depth=2)
            self.assertEqual(map_data, expected_return_value)
            calls_to_rm = self.village_manager.request_manager.method_calls
            self.assertEqual(len(calls_to_rm), 5)
            self.assertIn(call.get_map_overview(1, 1, 1), calls_to_rm)
            self.assertIn(call.get_map_overview(10000, 0, 0), calls_to_rm)
            self.assertIn(call.get_map_overview(10001, 0, 1000), calls_to_rm)
            self.assertIn(call.get_map_overview(10002, 1000, 0), calls_to_rm)
            self.assertIn(call.get_map_overview(10003, 1000, 1000), calls_to_rm)
            # refresh calls to request_manager:
            self.village_manager.request_manager.method_calls = []
            # 4 case: 2 farming centers in distinct sectors, map_depth=2.
            # expected: _get_map_overview is called 10 times (each center &
            # 4 area corners for each center. return value = merged sectors data
            self.village_manager.map_parser.collect_sector_data.return_value = \
                [{(1, 1): ['1001'], (3, 3): ['1003'], (1000, 1000): ['10003']},
                 {(2, 2): ['1002'], (4, 4): ['1004'], (5, 5): ['1005']},
                 {(8, 8): ['1008'], (10, 10): ['1010'], (6, 6): ['1006']},
                 {(0, 0): ['10000'], (0, 1000): ['10001'], (1000, 0): ['10002']}]
            map_data = self.village_manager._get_map_data(distinct_centers, map_depth=2)
            self.assertEqual(map_data, expected_return_value)
            calls_to_rm = self.village_manager.request_manager.method_calls
            expected_calls = [call.get_map_overview(1, 1, 1),
                              call.get_map_overview(2, 2, 2),
                              call.get_map_overview(10000, 0, 0),
                              call.get_map_overview(10000, 0, 0),
                              call.get_map_overview(10001, 0, 1000),
                              call.get_map_overview(10001, 0, 1000),
                              call.get_map_overview(10002, 1000, 0),
                              call.get_map_overview(10002, 1000, 0),
                              call.get_map_overview(10003, 1000, 1000),
                              call.get_map_overview(10003, 1000, 1000)]
            self.assertCountEqual(expected_calls, calls_to_rm)

    def test_filter_distinct_centers(self):
        """
        Possible situations:
        1) All farming centers lie in the same sector as
        current attacker: expected return = [] (empty list)
        2) All farming centers lie in different sectors
        from attacker: expected return = list with all centers,
        current attacker not in returned list
        3) Some farming centers do lie in the same sector as
        current attacker and some centers do not. expected
        return: list with centers that do not lie in attacker's
        sector, attacker is not in returned list.
        Expected returned type = list of tuples, where each tuple
        is (x, y) coordinates
        """
        current_attacker = (1, 1)
        centers = [((2, 2), 'a'), ((3, 3), 'b'), ((4, 4), 'c'), ((5, 5), 'd')]
        # some non-centers point added for plausibility
        all_in_one_data = [{(1, 1): '', (2, 2): '', (3, 3): '',
                            (4, 4): '', (5, 5): ''}, {(6, 6): '', (7, 7): ''}]
        distinct_centers = self.village_manager._filter_distinct_centers(
            current_attacker, centers, all_in_one_data)
        self.assertEqual(distinct_centers, [])

        all_in_separate = [{(1, 1): '', (10, 10): ''}, {(2, 2): '', (3, 3): ''},
                           {(4, 4): '', (8, 8): '', (10, 10): '', (5, 5): ''}]
        distinct_centers = self.village_manager._filter_distinct_centers(
            current_attacker, centers, all_in_separate)
        self.assertCountEqual(distinct_centers, centers)

        in_same_and_separate = [{(1, 1): '', (2, 2): '', (3, 3): ''},
                                {(4, 4): '', (7, 7): '', (9, 9): ''},
                                {(5, 5): '', (6, 6): ''}]
        distinct_centers = self.village_manager._filter_distinct_centers(
            current_attacker, centers, in_same_and_separate)
        self.assertCountEqual(distinct_centers, [((4, 4), 'c'), ((5, 5), 'd')])

    def test_merge_sectors_data(self):
        sectors_data_unique = [{(1, 1): 'test11', (2, 2): 'test22'},
                               {(3, 3): 'test33', (4, 4): 'test44'}]
        expected = {(1, 1): 'test11', (2, 2): 'test22',
                    (3, 3): 'test33', (4, 4): 'test44'}
        actual = self.village_manager._merge_sectors_data(sectors_data_unique)
        self.assertTrue(expected, actual)

        sectors_data_non_unique = [{(1, 1): 'test11', (2, 2): 'test22'},
                                   {(1, 1): 'test33', (4, 4): 'test44'}]
        expected = {(1, 1): 'test33', (2, 2): 'test22',  (4, 4): 'test44'}
        actual = self.village_manager._merge_sectors_data(sectors_data_non_unique)
        self.assertTrue(expected, actual)

    def test_is_valid_target(self):
        # [2] = village_name ("Bonus village" for bonus villages
        # & 0 for barbarian villages)
        # [4] = owner ('0' if no owner)
        v_data_barbarian = ['150281', 4, 0, '128', '0', '100']
        check = self.village_manager._is_valid_target(v_data_barbarian)
        self.assertTrue(check)

        v_data_player = ['153507', 5, 'lucien88s village', '85', '9141558', '100']
        check = self.village_manager._is_valid_target(v_data_player)
        self.assertFalse(check)

        v_data_bonus_wo_owner = ['150639', 16, 'Bonus village', '103', '0',
                                 '100', ['33% faster recruitment in the stables',
                                         'bonus/stable.png']]
        check = self.village_manager._is_valid_target(v_data_bonus_wo_owner)
        self.assertTrue(check)
        v_data_bonus_w_owner = ['150639', 16, 'Bonus village', '103', '1000000',
                                 '100', ['33% faster recruitment in the stables',
                                         'bonus/stable.png']]
        check = self.village_manager._is_valid_target(v_data_bonus_w_owner)
        self.assertFalse(check)

    def test_build_target_village(self):
        """
        Checks TargetVillage construction with valid input.
        All input (village_data) for TargetVillages construction
        is received by parsing Game's map overview pages. If
        Game will start to provide village_data that is structured
        in a different way, it will be not enough to just handle
        'TypeError' on this method level.
        """
        villa_coords = (1, 1)
        # [0] = id_, [3] = population. Other values are not needed
        village_data_wo_bonus = ['157956', 5, 'Guest201197s village',
                                 '40', '10201197', '100']
        villa = self.village_manager._build_target_village(villa_coords,
                                                           village_data_wo_bonus)
        self.assertIsInstance(villa, TargetVillage)
        self.assertEqual(villa.coords, villa_coords)
        self.assertEqual(villa.id, 157956)  # str id is converted to int
        self.assertEqual(villa.population, 40)  # as well as population
        self.assertIsNone(villa.bonus)

        # [6] = bonus data; [6][0] = str bonus, [6][1] = picture for bonus
        # (not needed)
        village_data_w_bonus = ['147081', 16, 'Bonus village', '101', '0',
                                '100',
                                ['30% more resources are produced (all '
                                 'resource types)', 'bonus/all.png']]
        villa = self.village_manager._build_target_village(villa_coords,
                                                           village_data_w_bonus)
        self.assertIsInstance(villa, TargetVillage)
        self.assertEqual(villa.coords, villa_coords)
        self.assertEqual(villa.id, 147081)
        self.assertEqual(villa.population, 101)
        self.assertEqual(villa.bonus, village_data_w_bonus[6][0])

    def test_get_map_overview(self):
        villa_id = 1
        x = y = 0
        self.village_manager._get_map_overview(villa_id, x, y)
        # village_manager.lock is acquired/released only once,
        # upon village_manager __init__. _get_map_overview() method
        # call doesn't acquire lock.
        expected_lock_calls = [call.acquire(), call.release()]
        self.assertEqual(expected_lock_calls,
                         self.village_manager.lock.method_calls)
        self.village_manager.request_manager.get_map_overview.\
            assert_called_once_with(villa_id, x, y)

    def test_get_train_screen(self):
        villa_id = 1
        self.village_manager._get_train_screen(villa_id)
        # village_manager.lock is acquired/released once
        # upon __init__ + this method call
        expected_lock_calls = [call.acquire(), call.release(),
                               call.acquire(), call.release()]
        self.assertEqual(expected_lock_calls,
                         self.village_manager.lock.method_calls)
        self.village_manager.request_manager.get_train_screen.\
            assert_called_once_with(villa_id)

    def test_get_overviews_screen(self):
        self.village_manager._get_overviews_screen()
        # village_manager.lock is acquired/released once
        # upon __init__ + this method call
        expected_lock_calls = [call.acquire(), call.release(),
                               call.acquire(), call.release()]
        self.assertEqual(expected_lock_calls,
                         self.village_manager.lock.method_calls)
        # ._get_overviews_screen is called once upon __init__
        # (.build_player_villages()) + with this method call
        expected_rm_calls = [call.get_overviews_screen(),
                             call.get_overviews_screen()]
        self.assertEqual(expected_rm_calls,
                         self.village_manager.request_manager.method_calls)

    def test_get_village_overview(self):
        villa_id = 1
        self.village_manager._get_village_overview(villa_id)
        # village_manager.lock is acquired/released once
        # upon __init__ + this method call
        expected_lock_calls = [call.acquire(), call.release(),
                               call.acquire(), call.release()]
        self.assertEqual(expected_lock_calls,
                         self.village_manager.lock.method_calls)
        self.village_manager.request_manager.get_village_overview.\
            assert_called_once_with(villa_id)


# class TestPlayerVillage(unittest.TestCase):
#
#     def setUp(self):
#         with open('test_html/village_overview_test_pv_initial.html') as f:
#             self.overview_html_init = f.read()
#         with open('test_html/village_overview_test_pv_updated.html') as f:
#             self.overview_html_updated = f.read()
#         with open('test_html/train_screen.html') as f:
#             self.train_html = f.read()
#
#     def test_initial_troops(self):
#         pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, False, 4)
#         correct_troops_to_use = ['axe', 'spy', 'light', 'marcher', 'heavy']
#         self.assertEqual(correct_troops_to_use, pv.troops_to_use)
#         self.assertEqual(pv.troops_count['axe'], 33)
#         self.assertEqual(pv.troops_count['spy'], 395)
#         self.assertEqual(pv.troops_count['light'], 9)
#         self.assertEqual(pv.troops_count['marcher'], 18)
#         self.assertEqual(pv.troops_count['heavy'], 129)
#         pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, True, 4)
#         correct_troops_to_use = ['spear', 'sword', 'archer', 'axe', 'spy', 'light', 'marcher', 'heavy']
#         self.assertEqual(correct_troops_to_use, pv.troops_to_use)
#         self.assertEqual(pv.troops_count['axe'], 33)
#         self.assertEqual(pv.troops_count['spy'], 395)
#         self.assertEqual(pv.troops_count['light'], 9)
#         self.assertEqual(pv.troops_count['marcher'], 18)
#         self.assertEqual(pv.troops_count['heavy'], 129)
#         self.assertEqual(pv.troops_count['spear'], 370)
#         self.assertEqual(pv.troops_count['sword'], 458)
#         self.assertEqual(pv.troops_count['archer'], 117)
#
#     def test_set_preferred_farm_radius(self):
#         pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, True, 4)
#         self.assertEqual(pv.radius, 21.87)
#         pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, False, 3)
#         self.assertEqual(pv.radius, 17.05)
#
#     def test_update_troops_count(self):
#         pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, True, 4)
#         with open('test_html/train_screen_update.html') as f:
#             train_html_updated = f.read()
#         pv.update_troops_count(train_screen_html=train_html_updated)
#         self.assertEqual(pv.troops_count['axe'], 95)
#         self.assertEqual(pv.troops_count['spy'], 393)
#         self.assertEqual(pv.troops_count['light'], 0)
#         self.assertEqual(pv.troops_count['marcher'], 36)
#         self.assertEqual(pv.troops_count['heavy'], 298)
#         self.assertEqual(pv.troops_count['spear'], 173)
#         self.assertEqual(pv.troops_count['sword'], 200)
#         self.assertEqual(pv.troops_count['archer'], 146)
#         troops_sent = {'spear': 100, 'axe': 95, 'heavy': 10, 'spy': 2}
#         pv.update_troops_count(troops_sent=troops_sent)
#         self.assertEqual(pv.troops_count['axe'], 0)
#         self.assertEqual(pv.troops_count['spy'], 391)
#         self.assertEqual(pv.troops_count['light'], 0)
#         self.assertEqual(pv.troops_count['marcher'], 36)
#         self.assertEqual(pv.troops_count['heavy'], 288)
#         self.assertEqual(pv.troops_count['spear'], 73)
#         self.assertEqual(pv.troops_count['sword'], 200)
#         self.assertEqual(pv.troops_count['archer'], 146)
#
#
# class TestVillage(unittest.TestCase):
#     """
#     Tests for bot's Village class. Uses stub object
#     instead of real AttackReport for .test_update_stats()
#     method.
#     """
#
#     def setUp(self):
#         self.barb = Village((200, 300), 10000, 100)
#         self.bonus_all = Village((100, 100), 10001,
#                                 "30% more resources are produced (all resource type)")
#         self.bonus_wood = Village((0, 0), 10002,
#                                  "100% higher wood production")
#         self.bonus_clay = Village((0, 100), 10003,
#                                  "100% higher clay production")
#         self.bonus_iron = Village((100, 0), 10004,
#                                  "100% higher iron production")
#
#     def test_get_rates_table(self):
#         rates = self.barb.get_rates_table()
#         self.assertIsInstance(rates, list)
#         self.assertIsInstance(rates[0], int)
#         self.assertEqual(len(rates), 31)
#
#     def test_set_h_rates(self):
#         self.barb.mine_levels = [10, 11, 12]
#         self.barb.set_h_rates()
#         self.assertTrue(self.barb.h_rates)
#         self.assertEqual(self.barb.h_rates[0], 117)
#         self.assertEqual(self.barb.h_rates[1], 136)
#         self.assertEqual(self.barb.h_rates[2], 158)
#
#         self.bonus_all.mine_levels = [9, 9, 9]
#         self.bonus_all.set_h_rates()
#         self.assertTrue(self.bonus_all.h_rates)
#         self.assertEqual(self.bonus_all.h_rates[0], 133)
#         self.assertEqual(self.bonus_all.h_rates[1], 133)
#         self.assertEqual(self.bonus_all.h_rates[2], 133)
#
#         self.bonus_wood.mine_levels = [1, 2, 3]
#         self.bonus_wood.set_h_rates()
#         self.assertTrue(self.bonus_wood.h_rates)
#         self.assertEqual(self.bonus_wood.h_rates[0], 60)
#         self.assertEqual(self.bonus_wood.h_rates[1], 35)
#         self.assertEqual(self.bonus_wood.h_rates[2], 41)
#
#         self.bonus_clay.mine_levels = [4, 5, 6]
#         self.bonus_clay.set_h_rates()
#         self.assertTrue(self.bonus_clay.h_rates)
#         self.assertEqual(self.bonus_clay.h_rates[0], 47)
#         self.assertEqual(self.bonus_clay.h_rates[1], 110)
#         self.assertEqual(self.bonus_clay.h_rates[2], 64)
#
#         self.bonus_iron.mine_levels = [20, 15, 8]
#         self.bonus_iron.set_h_rates()
#         self.assertTrue(self.bonus_iron.h_rates)
#         self.assertEqual(self.bonus_iron.h_rates[0], 530)
#         self.assertEqual(self.bonus_iron.h_rates[1], 249)
#         self.assertEqual(self.bonus_iron.h_rates[2], 172)
#
#     def test_estimate_capacity(self):
#         self.barb.mine_levels = [20, 20, 20]
#         self.barb.set_h_rates()
#         self.barb.last_visited = 10000
#         self.barb.remaining_capacity = 2000
#         self.assertEqual(self.barb.estimate_capacity(17200), 5180)
#
#         self.barb.remaining_capacity = 0
#         self.assertEqual(self.barb.estimate_capacity(17200), 3180)
#
#         self.barb.last_visited = None
#         three_h_production = sum(x * 3 for x in self.barb.h_rates)
#         t = time.mktime(time.gmtime())
#         t_to_arrival = t + 10800
#         self.assertEqual(self.barb.estimate_capacity(t_to_arrival), three_h_production)
#
#     def test_update_stats(self):
#         class dummy_report:
#             pass
#         report = dummy_report()
#         report.t_of_attack = 10000
#         report.mine_levels = [13, 14, 15]
#         report.remaining_capacity = 3000
#         report.looted_capacity = 4000
#
#         villa = Village((100, 200), 10005, 200)
#         villa.update_stats(report)
#         self.assertEqual(villa.last_visited, 10000)
#         self.assertEqual(villa.mine_levels, [13, 14, 15])
#         self.assertEqual(villa.h_rates, [184, 214, 249])
#         self.assertEqual(villa.remaining_capacity, 3000)
#         self.assertEqual(villa.looted["total"], 4000)
#
#         report = dummy_report()
#         report.t_of_attack = 20000
#         report.mine_levels = [17, 18, 19]
#         report.remaining_capacity = 0
#         report.looted_capacity = 7000
#
#         villa.update_stats(report)
#         self.assertEqual(villa.last_visited, 20000)
#         self.assertEqual(villa.mine_levels, [17, 18, 19])
#         self.assertEqual(villa.h_rates, [337, 391, 455])
#         self.assertEqual(villa.remaining_capacity, 0)
#         self.assertEqual(villa.looted["total"], 11000)
#         self.assertEqual(len(villa.looted["per_visit"]), 2)
#         self.assertEqual(villa.looted["per_visit"][-1][0], villa.last_visited)
#         self.assertEqual(villa.looted["per_visit"][-1][1], report.looted_capacity)
#
#     def test_is_fresh_meat(self):
#         fresh_villa = Village((100, 100), 100, 200)
#         self.assertTrue(fresh_villa.is_fresh_meat())
#         fresh_villa.last_visited = 1
#         self.assertFalse(fresh_villa.is_fresh_meat())
#
#     def test_passes_threshold(self):
#         fresh_villa = Village((100, 100), 100, 200)
#         threshold = 2400
#         fresh_villa.remaining_capacity = threshold - 1
#         self.assertFalse(fresh_villa.passes_threshold(threshold))
#         fresh_villa.remaining_capacity = threshold + 1
#         self.assertTrue(fresh_villa.passes_threshold(threshold))
#
#     def test_finished_rest(self):
#         fresh_villa = Village((100, 100), 100, 200)
#         rest = 3600
#         fresh_villa.last_visited = time.mktime(time.gmtime()) - (rest - 100)
#         self.assertFalse(fresh_villa.finished_rest(rest))
#         fresh_villa.last_visited = time.mktime(time.gmtime()) - (rest + 100)
#         self.assertTrue(fresh_villa.finished_rest(rest))
#
#    #
#    # def test_get_village(self):
#    #      villa_data = ['129795', 16, 'Bonus village', '247', '0', '100',
#    #                      ['30% more resources are produced (all resource types)', 'bonus/all.png']]
#    #      villa_coords = (100, 100)
#    #      villa = self.map.get_village(villa_coords, villa_data, 100)
#    #      self.assertEqual(villa.coords, villa_coords)
#    #      self.assertEqual(villa.bonus, villa_data[6][0])
#    #      self.assertEqual(villa.dist_from_base, 100)
#
#
#     # def test_is_valid(self):
#     #     non_valid = [['110479', 7, 'Claus laaan', '952', '10155826', '100'],
#     #                  ['128694', 18, 'Bonus village', '313', 'M140', '100', ['100% higher clay production', 'bonus/stone.png']]
#     #                  ]
#     #     valid = [['129120', 4, 0, '138', '0', '100'],
#     #              ['129795', 16, 'Bonus village', '247', '0', '100', ['30% more resources are produced (all resource types)', 'bonus/all.png']]
#     #              ]
#     #     for villa_data in non_valid:
#     #         self.assertFalse(self.map.is_valid(villa_data))
#     #     for villa_data in valid:
#     #         self.assertTrue(self.map.is_valid(villa_data))