import unittest
import os

import settings
from bot.libs.report_management import AttackReport


class TestAttackReport(unittest.TestCase):

    def setUp(self):
        self.test_data_path = os.path.join(settings.HTML_TEST_DATA_FOLDER,
                                           'reports/single_report_test_set')

    def test_green_report(self):
        """
        Most positive case: village was attacked w/o casualties
        and explored by scouts
        """
        filepath = os.path.join(self.test_data_path, 'en_report_green.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)
        self.assertEqual(rep.status, 'green')
        self.assertEqual(rep.coords, (203, 316))
        self.assertEqual(rep.t_of_attack, 1383480117)
        self.assertFalse(rep.defended)
        self.assertEqual(rep.mine_levels, [9, 1, 2])
        self.assertEqual(rep.remaining_capacity, 1686)
        self.assertEqual(rep.looted_capacity, 2400)
        self.assertEqual(rep.wall_level, 3)
        self.assertEqual(rep.storage_level, 3)

    def test_yellow_report(self):
        """
        Village was attacked with casualties (due to base defence
        and wall level) and explored.
        """
        filepath = os.path.join(self.test_data_path, 'en_report_yellow.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)
        self.assertEqual(rep.status, 'yellow')
        self.assertEqual(rep.coords, (222, 293))
        self.assertEqual(rep.t_of_attack, 1383407341)
        self.assertFalse(rep.defended)
        self.assertEqual(rep.mine_levels, [7, 4, 5])
        self.assertEqual(rep.remaining_capacity, 1656)
        self.assertEqual(rep.looted_capacity, 3120)
        self.assertEqual(rep.wall_level, 7)
        self.assertEqual(rep.storage_level, 4)

    def test_red_report(self):
        """
        This report type means that no one has returned:
        no information could be collected except of: 1) status
        of attack; 2) target coords; 3) t of attack.
        """
        filepath = os.path.join(self.test_data_path, 'en_report_red.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)

        self.assertEqual(rep.status, 'red')
        self.assertEqual(rep.coords, (220, 317))
        self.assertEqual(rep.t_of_attack, 1383659164)
        self.assertTrue(rep.defended)
        self.assertIsNone(rep.mine_levels)
        self.assertIsNone(rep.remaining_capacity)
        self.assertIsNone(rep.looted_capacity)
        self.assertIsNone(rep.wall_level)
        self.assertIsNone(rep.storage_level)

    def test_report_with_defence(self):
        """
        Tests reports for attacks that faced some defensive troops
        """
        filepath = os.path.join(self.test_data_path, 'en_report_yellow_w_defence.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)

        self.assertEqual(rep.status, 'yellow')
        self.assertEqual(rep.coords, (218, 310))
        self.assertEqual(rep.t_of_attack, 1385013774)
        self.assertTrue(rep.defended)
        self.assertEqual(rep.mine_levels, [11, 15, 10])
        self.assertEqual(rep.remaining_capacity, 450)
        self.assertEqual(rep.looted_capacity, 2800)
        self.assertEqual(rep.wall_level, 0)
        self.assertEqual(rep.storage_level, 5)

    def test_report_without_scouts(self):
        """
        Tests reports for attacks that were sent w/o scouts
        (so no info about remaining capacity or building levels
        could be collected).
        """
        filepath = os.path.join(self.test_data_path, 'en_report_yellow_wo_scouts.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)

        self.assertEqual(rep.status, 'yellow')
        self.assertEqual(rep.coords, (212, 297))
        self.assertEqual(rep.t_of_attack, 1384888276)
        self.assertFalse(rep.defended)
        self.assertEqual(rep.mine_levels, [0, 0, 0])
        self.assertEqual(rep.remaining_capacity, 0)
        self.assertEqual(rep.looted_capacity, 71)
        self.assertEqual(rep.wall_level, 0)
        self.assertIsNone(rep.storage_level)

    def test_scout_report(self):
        """
        Only scouts were sent in attack (so nothing was looted)
        """
        filepath = os.path.join(self.test_data_path, 'en_report_blue.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)

        self.assertEqual(rep.status, 'blue')
        self.assertEqual(rep.coords, (215, 301))
        self.assertEqual(rep.t_of_attack, 1383454750)
        self.assertFalse(rep.defended)
        self.assertEqual(rep.mine_levels, [11, 11, 9])
        self.assertEqual(rep.remaining_capacity, 2361)
        self.assertEqual(rep.looted_capacity, 0)
        self.assertEqual(rep.wall_level, 0)
        self.assertEqual(rep.storage_level, 8)

    def test_red_with_scouts_report(self):
        """
        All troops have died except scouts. Nothing was looted,
        but village was explored.
        """
        filepath = os.path.join(self.test_data_path, 'en_report_red_blue.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)

        self.assertEqual(rep.status, 'red_blue')
        self.assertEqual(rep.coords, (217, 311))
        self.assertEqual(rep.t_of_attack, 1385015263)
        self.assertTrue(rep.defended)
        self.assertEqual(rep.mine_levels, [11, 15, 7])
        self.assertEqual(rep.remaining_capacity, 4240)
        self.assertEqual(rep.looted_capacity, 0)
        self.assertEqual(rep.wall_level, 1)
        self.assertEqual(rep.storage_level, 11)

    def test_non_battle_report(self):
        """
        Tests non-battle reports (e.g. trade, support, achievemt).
        No info could be collected, so all AR attributes will remain
        'None'
        """
        filepath = os.path.join(self.test_data_path, 'en_report_support.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data)

        self.assertIsNone(rep.status)
        self.assertIsNone(rep.coords)
        self.assertIsNone(rep.t_of_attack)
        self.assertIsNone(rep.defended)
        self.assertIsNone(rep.mine_levels)
        self.assertIsNone(rep.remaining_capacity)
        self.assertIsNone(rep.looted_capacity)
        self.assertIsNone(rep.wall_level)
        self.assertIsNone(rep.storage_level)
