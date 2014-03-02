import unittest
import os
import time
from unittest.mock import Mock

import settings
from bot.libs.attack_management import *


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