import unittest
import os
import time
from unittest.mock import Mock, call

import settings
from bot.libs.attack_management import *
from bot.tests.factories import TargetVillageFactory


class TestDecisionMaker(unittest.TestCase):

    def test_get_next_attack_target(self):
        maker = DecisionMaker()
        # [{troops}, t_on_road]
        check_return_value = [{'unit_1': 10, 'spy': 1}, 10800]
        maker._is_attack_possible = Mock(return_value=check_return_value)
        villages = TargetVillageFactory.build_batch(2)
        # [(target, distance), ..]
        targets = [(villages[0], 10), villages[1], 20]
        troops = {'axe': 200, 'light': 300, 'spy': 20}
        t_limit = 3
        insert_spy = False

        next_target = maker.get_next_attack_target(available_targets=targets,
                                                   attacker_troops=troops,
                                                   t_limit=t_limit,
                                                   insert_spy=insert_spy)
        self.assertEqual(next_target,
                         [{'unit_1': 10, 'spy': 1}, 10800, villages[0].coords])

    def test_is_attack_possible(self):
        maker = DecisionMaker()
        maker._get_troops_map = Mock()
        maker._estimate_troops_needed = Mock()
        maker._get_time_on_the_road = Mock()
        attack_target = Mock()
        attack_target.estimate_capacity = Mock(return_value=None)
        units = [(Unit(name='a', attack=1, speed=20, haul=1), 10),
                 (Unit(name='b', attack=1, speed=10, haul=10), 10),
                 (Unit(name='c', attack=1, speed=10, haul=50), 100)]
        t_limit = 3 * 3600  # 3 hours
        troops_count = {}
        # 1 case: we have no units that could attack given target
        # (we have no unit which .speed * time_limit_to_leave >= distance)
        maker._get_troops_map.return_value = units
        maker._get_time_on_the_road.return_value = 100500
        check = maker._is_attack_possible(attack_target=attack_target,
                                          distance=50, t_limit=t_limit,
                                          troops_count=troops_count,
                                          insert_spy_in_attack=True)
        self.assertIsNone(check)
        self.assertCountEqual(maker._get_time_on_the_road.mock_calls,
                              [call(50, 20), call(50, 10), call(50, 10)])
        self.assertEqual(maker._estimate_troops_needed.mock_calls, [])
        # case 2: we have some units that may attack with a given
        # t_limit/radius, but attack_target.estimated_capacity is
        # to large, so we still cannot attack this target.
        maker._get_time_on_the_road.reset_mock()
        t_on_the_road = 2 * 3600
        maker._get_time_on_the_road.return_value = t_on_the_road
        maker._estimate_troops_needed.return_value = 200
        check = maker._is_attack_possible(attack_target=attack_target,
                                          distance=10, t_limit=t_limit,
                                          troops_count=troops_count,
                                          insert_spy_in_attack=True)
        self.assertIsNone(check)
        self.assertCountEqual(maker._get_time_on_the_road.mock_calls,
                              [call(10, 20), call(10, 10), call(10, 10)])
        self.assertEqual(len(maker._estimate_troops_needed.mock_calls), 3)
        # case 3: we have units that may attack. spy is not in 'units'
        # and cannot be inserted in attack group
        maker._get_time_on_the_road.reset_mock()
        maker._estimate_troops_needed.reset_mock()
        maker._estimate_troops_needed.return_value = 50
        check = maker._is_attack_possible(attack_target=attack_target,
                                          distance=5, t_limit=t_limit,
                                          troops_count=troops_count,
                                          insert_spy_in_attack=True)
        self.assertIsNotNone(check)
        self.assertCountEqual(maker._get_time_on_the_road.mock_calls,
                              [call(5, 20), call(5, 10), call(5, 10)])
        self.assertEqual(len(maker._estimate_troops_needed.mock_calls), 3)
        self.assertEqual(check, [{'c': 50}, t_on_the_road])
        # add scout
        troops_count = {'spy': 10}
        check = maker._is_attack_possible(attack_target=attack_target,
                                          distance=5, t_limit=t_limit,
                                          troops_count=troops_count,
                                          insert_spy_in_attack=True)
        self.assertIsNotNone(check)
        self.assertEqual(check, [{'c': 50, 'spy': 1}, t_on_the_road])

        check = maker._is_attack_possible(attack_target=attack_target,
                                          distance=5, t_limit=t_limit,
                                          troops_count=troops_count,
                                          insert_spy_in_attack=False)
        self.assertIsNotNone(check)
        self.assertEqual(check, [{'c': 50}, t_on_the_road])

    def test_get_troops_map(self):
        maker = DecisionMaker()
        troops_count = {'spy': 20, 'axe': 200, 'light': 200, 'marcher': 100}
        troops_map = maker._get_troops_map(troops_count)
        self.assertEqual(len(troops_map), 3)
        self.assertIsInstance(troops_map, list)
        slowest_unit = troops_map[0][0]
        self.assertEqual(slowest_unit.name, 'axe')


class TestAttackObserver(unittest.TestCase):

    def setUp(self):
        self.ao = AttackObserver(storage_type='local_file',
                                 storage_name='data_file')

    def test_restore_saved_attacks(self):
        """
        Test that saved arrivals and returns are correctly restored:
        1. all saved arrivals should be placed in ao.arrival_queue
        unchanged.
        2. only those saved returns, that are still in future, should
        be placed in ao.return_queue
        """
        now = time.mktime(time.gmtime())
        save_data_arrivals = {(1, 1): 1000, (2, 2): 2000, (3, 3): 3000}
        save_data_returns = {1: [now + 10, now + 20, now - 10],
                             2: [now + 10, now - 10, now - 20]}
        self.ao.storage.get_saved_arrivals = Mock(return_value=save_data_arrivals)
        self.ao.storage.get_saved_returns = Mock(return_value=save_data_returns)
        self.assertEqual(self.ao.arrival_queue, {})
        self.assertEqual(self.ao.return_queue, {})

        self.ao.restore_saved_attacks()
        self.assertEqual(self.ao.arrival_queue, save_data_arrivals)
        expected_returns = {1: [now + 10, now + 20], 2: [now + 10]}
        self.assertEqual(self.ao.return_queue, expected_returns)

    def test_is_someone_arrived(self):
        now = time.mktime(time.gmtime())
        # {(x, y): t_of_arrival, ..}
        arrival_queue = {(1, 1): now + 10, (2, 2): now + 20, (3, 3): now - 10,
                         (4, 4): now + 40, (5, 5): now - 50, (6, 6): now - 60}
        self.ao.arrival_queue = arrival_queue
        expected_arrived = 3  # number of arrived attacks (already in past)
        expected_not_arrived = {(1, 1): now + 10, (2, 2): now + 20, (4, 4): now + 40}

        arrived = self.ao.is_someone_arrived()
        self.assertEqual(arrived, expected_arrived)
        self.assertEqual(self.ao.arrival_queue, expected_not_arrived)

    def test_is_someone_returned(self):
        now = time.mktime(time.gmtime())
        # {attacker_id: [t_of_return_1, ..., t_of_return_n], ...]
        return_queue = {1: [now + 10, now + 20, now + 15, now - 10, now - 15],
                        2: [now - 20, now - 30, now - 15, now - 40, now + 5],
                        3: [now + 10, now + 5]}
        self.ao.return_queue = return_queue
        expected_returns = [1, 2]
        expected_not_returned = {1: [now + 10, now + 20, now + 15], 2: [now + 5],
                                 3: [now + 10, now + 5]}

        returned = self.ao.is_someone_returned()
        self.assertEqual(expected_returns, returned)
        self.assertEqual(self.ao.return_queue, expected_not_returned)

    def test_register_attack(self):
        self.assertEqual(self.ao.return_queue, {})
        self.assertEqual(self.ao.arrival_queue, {})
        self.ao.register_attack(attacker_id=1, coords=(1, 1), t_of_arrival=10,
                                t_of_return=20)
        self.assertEqual(self.ao.arrival_queue, {(1, 1): 10})
        self.assertEqual(self.ao.return_queue, {1: [20]})


class TestAttackHelper(unittest.TestCase):

    def setUp(self):
        self.ah = AttackHelper()

    def test_set_confirmation_token(self):
        filepath = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                'rally_point_screen.html')
        with open(filepath) as f:
            html_data = f.read()
        self.ah.set_confirmation_token(html_data)
        self.assertEqual(self.ah.confirmation_token,
                        ("f7f6174edf55e676607197", "5b6e5334f7f617"))

    def test_get_confirmation_data(self):
        self.ah.confirmation_token = ("f7f617", "5b6e5")
        self.ah._build_troops_data = Mock(return_value=[("spear", ''),
                                                        ("sword", 100),
                                                        ("spy", 10)])
        coords = (100, 100)
        expected_confirm_data = b"f7f617=5b6e5&template_id=&spear=&sword=100" \
                                b"&spy=10&x=100&y=100&attack=Attack"
        actual_data = self.ah.get_confirmation_data(coords=coords, troops={})
        self.assertEqual(expected_confirm_data, actual_data)

    def test_get_attack_data(self):
        self.ah._build_troops_data = Mock(return_value=[("spear", 0),
                                                        ("sword", 100),
                                                        ("spy", 10)])
        self.ah._get_ch_token = Mock(return_value=("ch", "abcdef"))
        self.ah._get_action_id = Mock(return_value=("action_id", "123456"))
        coords = (100, 100)
        expected_attack_data = b"attack=true&ch=abcdef&x=100&y=100&action_id=" \
                               b"123456&spear=0&sword=100&spy=10"
        actual_data = self.ah.get_attack_data(coords=coords, troops={},
                                              confirmation_screen="html")
        self.assertEqual(expected_attack_data, actual_data)

    def test_get_csrf_token(self):
        filepath = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                'confirmation_screen.html')
        with open(filepath) as f:
            html_data = f.read()
        expected_csrf = "3557"
        actual_csrf = self.ah.get_csrf_token(html_data)
        self.assertEqual(expected_csrf, actual_csrf)

    def test_get_action_id(self):
        filepath = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                'confirmation_screen.html')
        with open(filepath) as f:
            html_data = f.read()
        expected_id = ("action_id", "450375")
        actual_id = self.ah._get_action_id(html_data)
        self.assertEqual(expected_id, actual_id)

    def test_get_ch_token(self):
        filepath = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                'confirmation_screen.html')
        with open(filepath) as f:
            html_data = f.read()
        expected_ch = ("ch", "26f63c9a9789408efc45eaceb6c842554e280f73")
        actual_ch = self.ah._get_ch_token(html_data)
        self.assertEqual(expected_ch, actual_ch)

    def test_get_confirmation_token(self):
        filepath = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                'rally_point_screen.html')
        expected_token = ("f7f6174edf55e676607197", "5b6e5334f7f617")
        with open(filepath) as f:
            rally_html = f.read()
            self.ah.set_confirmation_token(rally_html)
        self.assertEqual(expected_token, self.ah.confirmation_token)

    def test_build_troops_data(self):
        troops = {"spear": 100, "spy": 2}
        expected_troops_data = [('spear', 100), ('sword', ''), ('axe', ''),
                                ('archer', ''), ('spy', 2), ('light', ''),
                                ('marcher', ''), ('heavy', ''), ('ram', ''),
                                ('catapult', ''), ('knight', ''),('snob', '')]
        troops_data = self.ah._build_troops_data(troops)
        self.assertEqual(expected_troops_data, troops_data)

        troops = {"axe": 100, "spy": 2, "light": 100, "marcher": 100, "heavy": 100}
        expected_troops_data = [('spear', 0), ('sword', 0), ('axe', 100),
                                ('archer', 0), ('spy', 2), ('light', 100),
                                ('marcher', 100), ('heavy', 100), ('ram', 0),
                                ('catapult', 0), ('knight', 0),('snob', 0)]
        troops_data = self.ah._build_troops_data(troops, empty=0)
        self.assertEqual(expected_troops_data, troops_data)