import os
import time
import unittest
import logging
from unittest.mock import Mock
from unittest.mock import patch

import settings
from bot.tests.factories import *
from bot.libs.village_management import *


# suppress messages, generated by intentional negative
# test inputs
logging.basicConfig(level=logging.CRITICAL)

class TestVillageManager(unittest.TestCase):

    def setUp(self):
        settings.DEBUG = True
        # Patch Storage class to avoid garbage-creation
        # (shelve file)
        with patch('bot.libs.village_management.Storage') as patched_storage:
            patched_storage.get_saved_villages.return_value = {}
            self.village_manager = VillageManager(storage_type='local_file',
                                                  storage_name='map_data')

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
        self.village_manager.build_target_villages(map_data, trusted_targets=[],
                                                   untrusted_targets=[],
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

        self.village_manager.build_target_villages(map_data, trusted_targets=[],
                                                   untrusted_targets=[],
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
        self.village_manager.map_storage.get_saved_villages.return_value = \
            saved_villages
        trusted_targets = [(3, 3), (4, 4)]

        self.village_manager.build_target_villages(map_data,
                                                   trusted_targets=trusted_targets,
                                                   untrusted_targets=[],
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
        # village that wasn't in map data is not in target list
        self.assertNotIn((5, 5), target_villages)

        # 4th case: both 'valid' villages are untrusted, both
        # 'invalid' villages are trusted
        untrusted_targets = [(1, 1), (2, 2)]
        self.village_manager.build_target_villages(map_data,
                                                   trusted_targets=trusted_targets,
                                                   untrusted_targets=untrusted_targets,
                                                   server_speed=1)
        target_villages = self.village_manager.target_villages
        self.assertNotIn((1, 1), target_villages)
        self.assertNotIn((2, 2), target_villages)
        self.assertIn((3, 3), target_villages)
        target_village = target_villages[(3, 3)]
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100002)
        self.assertIn((4, 4), target_villages)
        target_village = target_villages[(4, 4)]
        self.assertIsInstance(target_village, TargetVillage)
        self.assertEqual(target_village.id, 100003)

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
        self.assertEqual(attacker.id, 2000)

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
        filename = os.path.join(settings.TEST_DATA_FOLDER,
                                'html',
                                'net_villages_overviews-1.html')
        with open(filename) as f:
            overviews_data = f.read()
        expected_res = [(127591, (211, 305), 'Lounge of trolls'),
                        (135035, (210, 305), 'Feast of trolls'),
                        (135083, (211, 306), 'Cave of trolls'),
                        (126583, (211, 307), 'Piles of trolls'),
                        (136329, (212, 305), 'Shame of trolls'),]
        actual_res = self.village_manager._get_villages_data(overviews_data)
        self.assertCountEqual(expected_res, actual_res)
        filename = os.path.join(settings.TEST_DATA_FOLDER,
                                'html',
                                'net_villages_overviews-2.html')
        with open(filename) as f:
            overviews_data = f.read()
        expected_res = [(41940, (504, 306), 'ProperBills village')]
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

    def setUp(self):
        filepath = os.path.join(settings.TEST_DATA_FOLDER,
                                'html',
                                'train_screen.html')
        with open(filepath) as f:
            train_screen_html = f.read()
        self.data = train_screen_html
        self.unit_names = ["spear", "sword", "axe", "archer", "spy", "light",
                           "heavy", "marcher", "ram", "catapult"]

    def test_update_troops_count(self):
        pv = PlayerVillageFactory()

        pv.troops_to_use = self.unit_names
        pv.update_troops_count(html_data=self.data)
        troops = pv.troops_count
        self.assertEqual(troops["spear"], 370)
        self.assertEqual(troops["sword"], 458)
        self.assertEqual(troops["axe"], 33)
        self.assertEqual(troops["archer"], 117)
        self.assertEqual(troops["spy"], 395)
        self.assertEqual(troops["light"], 9)
        self.assertEqual(troops["marcher"], 18)
        self.assertEqual(troops["heavy"], 129)
        self.assertEqual(troops["ram"], 3)
        self.assertEqual(troops["catapult"], 0)

        pv.troops_to_use = ["light", "axe"]
        pv.update_troops_count(html_data=self.data)
        troops = pv.troops_count
        self.assertEqual(len(troops), 2)
        self.assertEqual(troops["axe"], 33)
        self.assertEqual(troops["light"], 9)

        troops_sent = {"axe": 20, "light": 9}
        pv.update_troops_count(troops_sent=troops_sent)
        troops = pv.troops_count
        self.assertEqual(troops["axe"], 13)
        self.assertEqual(troops["light"], 0)

    def test_get_troops_data(self):
        pv = PlayerVillageFactory()
        troops_data = pv._get_troops_data(self.data)
        for unit_name in self.unit_names:
            self.assertIn(unit_name, troops_data)


class TestVillage(unittest.TestCase):
    """
    Tests for bot's Village class. Uses stub object
    instead of real AttackReport for .test_update_stats()
    method.
    """
    def setUp(self):
        self.village = TargetVillage(coords=(1, 1), id_=1001, population=100,
                                     bonus=None, server_speed=1)

    def test_update_stats(self):
        village = self.village
        # stub ._set_h_rates to disable internal calls of this method
        village._set_h_rates = Mock(return_value=[100, 100, 100])

        new_report = Mock()
        config = {'t_of_attack': 1000, 'defended': True,
                  'mine_levels': [10, 10, 10], 'remaining_capacity': 1000,
                  'looted_capacity': 2000, 'storage_level': 5,
                  'wall_level': None}
        new_report.configure_mock(**config)
        village.update_stats(new_report)
        self.assertEqual(village.last_visited, 1000)
        self.assertTrue(village.defended)
        self.assertEqual(village.mine_levels, [10, 10, 10])
        self.assertEqual(village.remaining_capacity, 1000)
        self.assertIsNotNone(village.storage_limit)
        self.assertIsNone(village.base_defence)
        self.assertEqual(village.total_loot, 2000)
        self.assertEqual(len(village.visits_history), 1)
        self.assertEqual(village.visits_history[0],
                         (config['t_of_attack'], config['looted_capacity']))

        new_report = Mock()
        config['t_of_attack'] = 2000
        config['defended'] = False
        config['mine_levels'] = [0, 0, 12]
        config['remaining_capacity'] = 0
        config['wall_level'] = 5
        new_report.configure_mock(**config)
        village.update_stats(new_report)
        self.assertEqual(village.last_visited, 2000)
        self.assertFalse(village.defended)
        # mine levels were not lowered
        self.assertEqual(village.mine_levels, [10, 10, 12])
        self.assertEqual(village.remaining_capacity, 0)
        self.assertIsNotNone(village.storage_limit)
        self.assertIsNotNone(village.base_defence)
        self.assertEqual(village.total_loot, 4000)
        self.assertEqual(len(village.visits_history), 2)
        self.assertEqual(village.visits_history[0],
                         (config['t_of_attack'], config['looted_capacity']))

    def test_estimate_capacity(self):
        self.village._get_default_capacity = Mock(return_value=1000)
        # no h/rates, return value = default capacity
        self.assertEqual(self.village.estimate_capacity(t_of_arrival=1), 1000)
        # base scenario: village has rested 5 hours, there was no
        # remaining capacity & there is no storage limit
        self.village.h_rates = [100, 100, 100]
        self.village.last_visited = 0
        t_of_arrival = 3600 * 5
        estimate = self.village.estimate_capacity(t_of_arrival)
        self.assertEqual(estimate, 1500)
        # remaining capacity should be added to estimate
        self.village.remaining_capacity = 1000
        estimate = self.village.estimate_capacity(t_of_arrival)
        self.assertEqual(estimate, 2500)
        # 8 hours is "hard-cap" (somebody in area has certainly
        # farmed this village)
        t_of_arrival = 3600 * 20
        estimate = self.village.estimate_capacity(t_of_arrival)
        self.assertEqual(estimate, 3400)
        # storage limit "burns" resources
        self.village.storage_limit = 3000
        estimate = self.village.estimate_capacity(t_of_arrival)
        self.assertEqual(estimate, 3000)

    def test_has_finished_rest(self):
        rest_interval = 3
        # no info about last visit
        self.assertIsNone(self.village.finished_rest(rest_interval))
        # visited 2 hours ago
        self.village.last_visited = time.mktime(time.gmtime()) - 2 * 3600
        self.assertFalse(self.village.finished_rest(rest_interval))
        # visited 4 hours ago
        self.village.last_visited = time.mktime(time.gmtime()) - 4 * 3600
        self.assertTrue(self.village.finished_rest(rest_interval))

    def test_has_valuable_loot(self):
        rest_interval = 3
        # village wo info about h/rates & remaining capacity
        self.assertIsNone(self.village.has_valuable_loot(rest_interval))
        # remaining = h/rates * 4 hours
        self.village.h_rates = [100, 100, 100]
        self.village.remaining_capacity = 1200
        self.assertTrue(self.village.has_valuable_loot(rest_interval))
        # remaining = h/rates * 2 hours (less than rest_interval)
        self.village.remaining_capacity = 600
        self.assertFalse(self.village.has_valuable_loot(rest_interval))

    def test_set_hour_rates(self):
        # call with mine_levels = None
        self.village._set_h_rates()
        self.assertIsNone(self.village.h_rates)
        # rate_multiplier = 1
        self.village.mine_levels = [10, 10, 10]
        self.village._set_h_rates()
        self.assertEqual(self.village.h_rates, [117, 117, 117])
        # bonuses, multipliers
        self.village.bonus = "30% more resources are produced [all resource types]"
        self.village.rate_multiplier = 1.25
        self.village.mine_levels = [9, 9, 9]
        self.village._set_h_rates()
        self.assertEqual(self.village.h_rates, [162, 162, 162])

        self.village.bonus = "100% higher wood production"
        self.village.rate_multiplier = 1.5
        self.village._set_h_rates()
        self.assertEqual(self.village.h_rates, [300, 150, 150])

        self.village.bonus = "100% higher clay production"
        self.village._set_h_rates()
        self.assertEqual(self.village.h_rates, [150, 300, 150])

        self.village.bonus = "100% higher iron production"
        self.village.rate_multiplier = 2
        self.village._set_h_rates()
        self.assertEqual(self.village.h_rates, [200, 200, 400])

    def test_get_rates_table(self):
        rates = self.village._get_mine_rates()
        self.assertIsInstance(rates, list)
        self.assertIsInstance(rates[0], int)
        self.assertEqual(len(rates), 31)
        self.assertEqual(rates[30], 2400)

    def test_get_storage_rates(self):
        rates = self.village._get_storage_rates()
        self.assertIsInstance(rates, list)
        self.assertIsInstance(rates[0], int)
        self.assertEqual(len(rates), 30)
        self.assertEqual(rates[0], 1000)
        self.assertEqual(rates[29], 400000)
