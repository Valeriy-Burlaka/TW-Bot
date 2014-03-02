import unittest
import os
from unittest.mock import Mock

import settings
from bot.libs.attack_management import AttackHelper


class TestAttackHelper(unittest.TestCase):

    def setUp(self):
        self.ah = AttackHelper()



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