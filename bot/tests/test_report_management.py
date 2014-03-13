import unittest
import os

import settings
from bot.app import locale
from bot.libs.report_management import AttackReport
from bot.libs.report_management import ReportManager


class TestReportManager(unittest.TestCase):

    def setUp(self):
        self.test_data_path = os.path.join(settings.TEST_DATA_FOLDER,
                                           'html',
                                           'reports/report_page_test_set')

    def test_get_report_urls(self):
        rm = ReportManager(locale={})
        filename = os.path.join(self.test_data_path,
                                'en_report-page_w_new_battle.html')
        with open(filename) as f:
            html_data = f.read()
        # get only 'new' reports:
        expected_urls = [
            '/game.php?village=127591&mode=all&view=65471139&screen=report',
            '/game.php?village=127591&mode=all&view=65470230&screen=report',
            '/game.php?village=127591&mode=all&view=65466313&screen=report',
            '/game.php?village=127591&mode=all&view=65462611&screen=report',
            '/game.php?village=127591&mode=all&view=65456252&screen=report'
        ]
        actual_urls = rm.get_report_urls(html_data)
        self.assertCountEqual(expected_urls, actual_urls)
        # get both 'new' and not 'new'
        not_new_reports = [
            '/game.php?village=127591&mode=all&view=65454256&screen=report',
            '/game.php?village=127591&mode=all&view=65451253&screen=report',
            '/game.php?village=127591&mode=all&view=65450705&screen=report',
            '/game.php?village=127591&mode=all&view=65448219&screen=report',
            '/game.php?village=127591&mode=all&view=65447724&screen=report',
            '/game.php?village=127591&mode=all&view=65445091&screen=report',
            '/game.php?village=127591&mode=all&view=65444232&screen=report'
        ]
        expected_urls.extend(not_new_reports)
        actual_urls = rm.get_report_urls(html_data, only_new=False)
        self.assertCountEqual(expected_urls, actual_urls)

        filename = os.path.join(self.test_data_path,
                                'en_report-page_w_new_support.html')
        with open(filename) as f:
            html_data = f.read()
        expected_urls = [
            '/game.php?village=127591&mode=all&view=65518754&screen=report',
            '/game.php?village=127591&mode=all&view=65518624&screen=report',
            '/game.php?village=127591&mode=all&view=65512571&screen=report',
            '/game.php?village=127591&mode=all&view=65511688&screen=report'
        ]
        actual_urls = rm.get_report_urls(html_data)
        self.assertCountEqual(expected_urls, actual_urls)

        not_new_reports = [
            '/game.php?village=127591&mode=all&view=65517350&screen=report',
            '/game.php?village=127591&mode=all&view=65517299&screen=report',
            '/game.php?village=127591&mode=all&view=65517137&screen=report',
            '/game.php?village=127591&mode=all&view=65515964&screen=report',
            '/game.php?village=127591&mode=all&view=65509197&screen=report',
            '/game.php?village=127591&mode=all&view=65508754&screen=report',
            '/game.php?village=127591&mode=all&view=65508039&screen=report',
            '/game.php?village=127591&mode=all&view=65507562&screen=report'
        ]
        expected_urls.extend(not_new_reports)
        actual_urls = rm.get_report_urls(html_data, only_new=False)
        self.assertCountEqual(expected_urls, actual_urls)

    def test_build_report(self):
        rm = ReportManager(locale=locale.LOCALE["en"])
        filepath = os.path.join(settings.TEST_DATA_FOLDER,
                                'html',
                                'reports/single_report_test_set',
                                'en_report_green.html')
        with open(filepath) as f:
            html_data = f.read()
        report = rm.build_report(html_data)
        self.assertIsInstance(report, AttackReport)


class TestAttackReport(unittest.TestCase):

    def setUp(self):
        self.test_data_path = os.path.join(settings.TEST_DATA_FOLDER,
                                           'html',
                                           'reports/single_report_test_set')
        self.locale = locale.LOCALE

    def test_green_report(self):
        """
        Most positive case: village was attacked w/o casualties
        and explored by scouts
        """
        filepath = os.path.join(self.test_data_path, 'en_report_green.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data, self.locale["en"])
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
            rep = AttackReport(report_data, self.locale["en"])
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
            rep = AttackReport(report_data, self.locale["en"])

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
            rep = AttackReport(report_data, self.locale["en"])

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
            rep = AttackReport(report_data, self.locale["en"])

        self.assertEqual(rep.status, 'yellow')
        self.assertEqual(rep.coords, (212, 297))
        self.assertEqual(rep.t_of_attack, 1384888276)
        self.assertFalse(rep.defended)
        self.assertEqual(rep.mine_levels, [0, 0, 0])
        self.assertEqual(rep.remaining_capacity, 0)
        self.assertEqual(rep.looted_capacity, 71)
        self.assertEqual(rep.wall_level, 0)
        self.assertEqual(rep.storage_level, 0)

    def test_scout_report(self):
        """
        Only scouts were sent in attack (so nothing was looted)
        """
        filepath = os.path.join(self.test_data_path, 'en_report_blue.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data, self.locale["en"])

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
            rep = AttackReport(report_data, self.locale["en"])

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
            rep = AttackReport(report_data, self.locale["en"])

        self.assertIsNone(rep.status)
        self.assertIsNone(rep.coords)
        self.assertIsNone(rep.t_of_attack)
        self.assertIsNone(rep.defended)
        self.assertIsNone(rep.mine_levels)
        self.assertIsNone(rep.remaining_capacity)
        self.assertIsNone(rep.looted_capacity)
        self.assertIsNone(rep.wall_level)
        self.assertIsNone(rep.storage_level)

    def test_incorrect_report_data(self):
        """
        Checks that AR gracefully handles bad input data
        """
        rep = AttackReport('foo bar eggs spam!!!!', locale=None)
        self.assertIsNone(rep.status)
        self.assertIsNone(rep.coords)
        self.assertIsNone(rep.t_of_attack)
        self.assertIsNone(rep.defended)
        self.assertIsNone(rep.mine_levels)
        self.assertIsNone(rep.remaining_capacity)
        self.assertIsNone(rep.looted_capacity)
        self.assertIsNone(rep.wall_level)
        self.assertIsNone(rep.storage_level)

    def test_fr_scout_report_defended(self):
        filepath = os.path.join(self.test_data_path, 'fr_report_blue_defended.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data, self.locale["fr"])

        self.assertEqual(rep.status, 'blue')
        self.assertEqual(rep.coords, (621, 351))
        self.assertEqual(rep.t_of_attack, 1394144603)
        self.assertTrue(rep.defended)
        self.assertEqual(rep.mine_levels, [3, 2, 1])
        self.assertEqual(rep.remaining_capacity, 3237)
        self.assertEqual(rep.looted_capacity, 0)
        self.assertEqual(rep.wall_level, 1)
        self.assertEqual(rep.storage_level, 2)

    def test_fr_report_yellow(self):
        filepath = os.path.join(self.test_data_path, 'fr_report_yellow.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data, self.locale["fr"])
        self.assertEqual(rep.status, 'yellow')
        self.assertEqual(rep.coords, (614, 352))
        self.assertEqual(rep.t_of_attack, 1394178196)
        self.assertFalse(rep.defended)
        self.assertEqual(rep.mine_levels, [6, 2, 1])
        self.assertEqual(rep.remaining_capacity, 0)
        self.assertEqual(rep.looted_capacity, 2202)
        self.assertEqual(rep.wall_level, 5)
        self.assertEqual(rep.storage_level, 4)

    def test_fr_green_report(self):
        filepath = os.path.join(self.test_data_path, 'fr_report_green.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data, self.locale["fr"])
        self.assertEqual(rep.status, 'green')
        self.assertEqual(rep.coords, (615, 349))
        self.assertEqual(rep.t_of_attack, 1394182293)
        self.assertFalse(rep.defended)
        self.assertEqual(rep.mine_levels, [5, 5, 8])
        self.assertEqual(rep.remaining_capacity, 3)
        self.assertEqual(rep.looted_capacity, 1182)
        self.assertEqual(rep.wall_level, 2)
        self.assertEqual(rep.storage_level, 6)

    def test_fr_red_report(self):
        filepath = os.path.join(self.test_data_path, 'fr_report_red.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data, self.locale["fr"])
        self.assertEqual(rep.status, 'red')
        self.assertEqual(rep.coords, (616, 351))
        self.assertEqual(rep.t_of_attack, 1394747077)
        self.assertTrue(rep.defended)
        self.assertIsNone(rep.mine_levels)
        self.assertIsNone(rep.remaining_capacity)
        self.assertIsNone(rep.looted_capacity)
        self.assertIsNone(rep.wall_level)
        self.assertIsNone(rep.storage_level)

    def test_us_red_report(self):
        filepath = os.path.join(self.test_data_path, 'us_report_red.html')
        with open(filepath) as f:
            report_data = f.read()
            rep = AttackReport(report_data, self.locale["en"])
        self.assertEqual(rep.status, 'red')
        self.assertEqual(rep.coords, (673, 511))
        self.assertEqual(rep.t_of_attack, 1394724838)
        self.assertTrue(rep.defended)
        self.assertIsNone(rep.mine_levels)
        self.assertIsNone(rep.remaining_capacity)
        self.assertIsNone(rep.looted_capacity)
        self.assertIsNone(rep.wall_level)
        self.assertIsNone(rep.storage_level)
