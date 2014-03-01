import unittest
import os

import settings
from bot.libs.attack_management import AttackHelper


class TestAttackHelper(unittest.TestCase):

    def setUp(self):
        self.ah = AttackHelper()


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