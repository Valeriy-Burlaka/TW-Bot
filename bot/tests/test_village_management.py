import os
import unittest
import logging
from unittest.mock import Mock
from unittest.mock import patch

import settings
from bot.tests.factories import PlayerVillageFactory, TargetVillageFactory
from bot.libs.village_management import *


# suppress messages, generated by intentional negative
# test inputs
logging.basicConfig(level=logging.CRITICAL)

class TestVillageManager(unittest.TestCase):

    def setUp(self):
        settings.DEBUG = True
        # Patch MapStorage class to avoid garbage-creation
        # (shelve file)
        with patch('bot.libs.village_management.MapStorage',
                        autospec=True) as patched_storage:
            patched_storage.get_saved_villages.return_value = {}
            self.village_manager = VillageManager(storage_type='local_file',
                                                  storage_file_name='map_data')

    def tearDown(self):
        settings.DEBUG = False

    def test_build_target_villages(self):
        self.assertEqual(self.village_manager.target_villages, {})
    #     # create map_data that contains both valid
    #     # (bonus/barb) & invalid villages (with owner != '0') villages
    #     # {(x, y): [village_data], ..} where village_data[0] = id,
    #     # [2] = name, [3] = population, [4] = owner ([1] & [5] - unused)
        map_data = {(1, 1): ['100000', 4, 0, '78', '0', '100'],
                    (2, 2): ['100001', 4, 'Bonus village', '125', '0', '100',
                             ['a', 'b']],
                    # invalid
                    (3, 3): ['100002', 5, 'Mordor', '666', 'non-empty', '100'],
                    (4, 4): ['100003', 5, 'Rohan', '777', 'non-empty', '100']}
        # 1 case, base scenarion: no saved villages, no trusted villages;
        # resulting .target_villages should contain 2 (valid) TargetVillages
        self.village_manager.build_target_villages(map_data, trusted_targets=(),
                                                   server_speed=1)

        target_villages = self.village_manager.target_villages
        self.assertEqual(len(target_villages), 2)
        self.assertIn((1, 1), target_villages)
        target_village = target_villages[(1, 1)]
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100000)
        self.assertEqual(target_village.coords, (1, 1))
        self.assertEqual(target_village.population, 78)
        self.assertEqual(target_village.rate_multiplier, 1)

        target_village = target_villages[(2, 2)]
        self.assertIn((2, 2), target_villages)
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100001)
        self.assertEqual(target_village.coords, (2, 2))
        self.assertEqual(target_village.population, 125)
        # 2 case, extended scenario: 2 saved villages (1 is knowingly
        # 'invalid'), no trusted villages.
        # expected: there are 2 villages in .target_villages;
        # target that was saved has updated info
        valid_saved = TargetVillage((1, 1), 100000, 10)
        valid_saved.h_rates = (10, 10, 10)
        invalid_saved = TargetVillage((3, 3), 100002, 10)
        invalid_saved.h_rates = (15, 15, 15)
        saved_villages = {(1, 1): valid_saved, (3, 3): invalid_saved}
        self.village_manager.map_storage.get_saved_villages.return_value = \
            saved_villages

        self.village_manager.build_target_villages(map_data, trusted_targets=(),
                                                   server_speed=1)

        target_villages = self.village_manager.target_villages
        self.assertEqual(len(target_villages), 2)
        self.assertIn((1, 1), target_villages)
        target_village = target_villages[(1, 1)]
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100000)
        self.assertEqual(target_village.coords, (1, 1))
        # village that was in saved retained data about h/rates
        self.assertEqual(target_village.h_rates, (10, 10, 10))
        self.assertEqual(target_village.population, 78)
        
        self.assertIn((2, 2), target_villages)
        target_village = target_villages[(2, 2)]
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100001)
        self.assertEqual(target_village.coords, (2, 2))
        # village that was not in saved still has no h_rates
        self.assertEqual(target_village.h_rates, None)
        self.assertEqual(target_village.population, 125)
        # 3 case, extended scenario 2: + 1 saved village, that will
        # not be in .map_data; .trusted_villages contains both
        # 'invalid' villages;
        # expected: there are 4 villages in .target_villages;
        # village that was not in .map_data is not picked from saved;
        # villages, that were in .map_data & were saved, have been updated
        never_found_village = TargetVillage((5, 5), 100005, 10)
        saved_villages[(5, 5)] = never_found_village
        trusted_targets = ((3, 3), (4, 4))

        self.village_manager.build_target_villages(map_data,
                                                   trusted_targets=trusted_targets,
                                                   server_speed=1)
        
        target_villages = self.village_manager.target_villages
        self.assertEqual(len(target_villages), 4)
        self.assertIn((1, 1), target_villages)
        target_village = target_villages[(1, 1)]
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100000)
        self.assertEqual(target_village.coords, (1, 1))
        # village that was in saved retained data about h/rates
        self.assertEqual(target_village.h_rates, (10, 10, 10))
        self.assertEqual(target_village.population, 78)

        target_village = target_villages[(2, 2)]
        self.assertIn((2, 2), target_villages)
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100001)
        self.assertEqual(target_village.coords, (2, 2))
        # village that was not in saved still has no h_rates
        self.assertEqual(target_village.h_rates, None)
        self.assertEqual(target_village.population, 125)

        # saved & trusted
        target_village = target_villages[(3, 3)]
        self.assertIn((3, 3), target_villages)
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100002)
        self.assertEqual(target_village.coords, (3, 3))
        self.assertEqual(target_village.h_rates, (15, 15, 15))
        self.assertEqual(target_village.population, 666)
        # not saved, trusted
        target_village = target_villages[(4, 4)]
        self.assertIn((4, 4), target_villages)
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100003)
        self.assertEqual(target_village.coords, (4, 4))
        self.assertEqual(target_village.h_rates, None)
        self.assertEqual(target_village.population, 777)

    def test_build_player_villages(self):
        villages_data = [(127591, (211, 305), 'Lounge of trolls'),
                         (135035, (210, 305), 'Feast of trolls')]
        self.village_manager._get_villages_data = Mock(return_value=villages_data)

        self.village_manager.build_player_villages('html')
        self.assertIn(127591, self.village_manager.player_villages)
        player_village = self.village_manager.player_villages[127591]
        self.assertIsInstance(player_village, PlayerVillage)
        self.assertEqual(player_village.id, villages_data[0][0])
        self.assertEqual(player_village.coords, villages_data[0][1])
        self.assertEqual(player_village.name, villages_data[0][2])

        self.assertIn(135035, self.village_manager.player_villages)
        player_village = self.village_manager.player_villages[135035]
        self.assertIsInstance(player_village, PlayerVillage)
        self.assertEqual(player_village.id, villages_data[1][0])
        self.assertEqual(player_village.coords, villages_data[1][1])
        self.assertEqual(player_village.name, villages_data[1][2])

    def test_set_farming_village(self):
        # .farming_villages & .player_villages are an empty dicts initially
        self.assertEqual(self.village_manager.farming_villages, {})
        self.assertEqual(self.village_manager.player_villages, {})
        # sanity check: if there no .player_villages, call to method
        # doesn't fail
        self.village_manager.set_farming_village(1, '')
        self.assertEqual(self.village_manager.farming_villages, {})
        # Fill .player_villages. PVFactory doesn't suffice here, because
        # we need to stub PlayerVillage methods
        pv1 = Mock(spec=PlayerVillage, id=1000, coords=(1, 1), attack_targets=[])
        self.village_manager.player_villages = {1000: pv1}

        attack_targets = [((1, 1), 10), ((2, 2), 11)]
        self.village_manager._get_targets_for_attacker = Mock(return_value=attack_targets)
        # call with default 'use_def' & 'heavy_is_def'
        self.village_manager.set_farming_village(1000, 'html')
        self.assertEqual(len(self.village_manager.farming_villages), 1)
        self.assertIn(1000, self.village_manager.farming_villages)
        attacker = self.village_manager.farming_villages[1000]
        attacker.set_troops_to_use.assert_called_once_with(False, False)
        attacker.update_troops_count.assert_called_once_with(html_data='html')
        attacker.set_attack_targets.assert_called_once_with(attack_targets)

        pv2 = Mock(spec=PlayerVillage, id=2000, coords=(2, 2), attack_targets=[])
        self.village_manager.player_villages[2000] = pv2

        self.village_manager.set_farming_village(2000, 'html',
                                                 use_def_to_farm=True,
                                                 heavy_is_def=True)
        self.assertEqual(len(self.village_manager.farming_villages), 2)
        self.assertIn(2000, self.village_manager.farming_villages)
        attacker = self.village_manager.farming_villages[2000]
        attacker.set_troops_to_use.assert_called_once_with(True, True)
        attacker.update_troops_count.assert_called_once_with(html_data='html')
        attacker.set_attack_targets.assert_called_once_with(attack_targets)

    def test_get_next_attacking_village(self):
        attack_targets = [(1, 1), (2, 2)]
        troops_count = {'spear': 1}
        pv1 = Mock(spec=PlayerVillage, id=1000, coords=(1, 1),
                   active=False, attack_targets=attack_targets)
        pv2 = Mock(spec=PlayerVillage, id=2000, coords=(2, 2),
                   active=True, attack_targets=attack_targets)

        pv2.get_troops_count = Mock(return_value=troops_count)
        self.assertEqual(len(self.village_manager.farming_villages), 0)
        self.village_manager.farming_villages = {1000: pv1, 2000: pv2}

        attacker = self.village_manager.get_next_attacking_village()
        self.assertEqual(attacker[0], 2000)
        self.assertEqual(attacker[1], troops_count)
        self.assertEqual(attacker[2], attack_targets)

        pv2.active = False
        attacker = self.village_manager.get_next_attacking_village()
        self.assertIsNone(attacker)

    def test_update_troops_count(self):
        pv1 = Mock(spec=PlayerVillage, id=1000, coords=(1, 1), active=False)
        self.village_manager.farming_villages = {1000: pv1}
        troops_sent = {'spear': 1}

        self.village_manager.update_troops_count(1000, troops_sent)
        pv1.update_troops_count.assert_called_once_with(troops_sent=troops_sent)

    def test_refresh_village_troops(self):
        pv1 = Mock(spec=PlayerVillage, id=1000, coords=(1, 1), active=False)
        self.village_manager.farming_villages = {1000: pv1}

        self.village_manager.refresh_village_troops(1000, 'html')
        pv1.update_troops_count.assert_called_once_with(html_data='html')
        self.assertTrue(pv1.active)

    def test_get_targets_for_attacker(self):
        self.assertEqual(self.village_manager.target_villages, {})
        attacker = PlayerVillageFactory()
        targets = TargetVillageFactory.build_batch(5)
        self.village_manager.target_villages = {target.coords: target for
                                                target in targets}
        attacker_coords = attacker.coords
        target_coords = self.village_manager.target_villages.keys()
        with patch('bot.libs.village_management.MapMath', autospec=True) as map_math:
            self.village_manager._get_targets_for_attacker(attacker)
            map_math.get_targets_by_distance.assert_called_once_with(attacker_coords,
                                                                     target_coords)

    def test_get_villages_data(self):
        filename = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                'villages_overviews.html')
        with open(filename) as f:
            overviews_data = f.read()
        expected_res = [(127591, (211, 305), 'Lounge of trolls'),
                        (135035, (210, 305), 'Feast of trolls'),
                        (135083, (211, 306), 'Cave of trolls'),
                        (126583, (211, 307), 'Piles of trolls'),
                        (136329, (212, 305), 'Shame of trolls'),]
        actual_res = self.village_manager._get_villages_data(overviews_data)
        self.assertCountEqual(expected_res, actual_res)

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
                                                           village_data_wo_bonus,
                                                           server_speed=1)
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
                                                           village_data_w_bonus,
                                                           server_speed=1)
        self.assertIsInstance(villa, TargetVillage)
        self.assertEqual(villa.coords, villa_coords)
        self.assertEqual(villa.id, 147081)
        self.assertEqual(villa.population, 101)
        self.assertEqual(villa.bonus, village_data_w_bonus[6][0])



class TestPlayerVillage(unittest.TestCase):
    pass



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