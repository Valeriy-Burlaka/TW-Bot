import time
import unittest
import shelve
from threading import Thread
from threading import Lock



class TestAttackQueue(unittest.TestCase):

    def setUp(self):
        self.aq = AttackQueue(211, 305, DummyRequestManager(), mapfile='test_data/testmap')
        self.report_builder = ReportBuilder(DummyRequestManager(), Lock())

    def test_base_attributes(self):
        pass

    def test_build_queue(self):
        self.assertTrue(self.aq.queue)
        self.assertIsInstance(self.aq.queue[0], Village)
        self.assertIsInstance(self.aq.queue[0].dist_from_base, float)
        coords = self.aq.queue[0].coords
        self.assertTrue(coords == (211,306) or coords == (212,305)) # 2 equally near villages in test data
        coords = self.aq.queue[2].coords # certainly 3rd village in test data
        self.assertTrue(coords == (212,306))

    def test_is_ready_for_farm(self):
        """Components under this function are covered in TestVillage
        class so just making a sanity test"""
        fresh_village = Village((100, 100), 100, 200)
        self.assertTrue(self.aq.is_ready_for_farm(fresh_village))

    def test_get_time_one_the_road(self):
        distance = 10
        speed = 10
        time_on_road = distance*speed*60
        self.assertEqual(self.aq.get_time_on_the_road(distance, speed), time_on_road)

    def test_estimate_arrival(self):
        time_on_road = 6000
        expected_arrival = time.mktime(time.gmtime()) + time_on_road
        self.assertAlmostEqual(expected_arrival, self.aq.estimate_arrival(time_on_road))

    def test_estimate_troops_needed(self):
        lc = Unit('light', 10, 80)
        self.assertEqual(self.aq.estimate_troops_needed(lc, 2400), 30)
        self.assertEqual(self.aq.estimate_troops_needed(lc, 4800), 60)

    def test_estimate_initial_capacity(self):
        villa = Village((1,1), 1, 91)
        self.assertEqual(self.aq.estimate_initial_capacity(villa), 1200)
        villa.population = 151
        self.assertEqual(self.aq.estimate_initial_capacity(villa), 2400)
        villa.population = 251
        self.assertEqual(self.aq.estimate_initial_capacity(villa), 3200)
        villa.population = 351
        self.assertEqual(self.aq.estimate_initial_capacity(villa), 4800)
        villa.population = 451
        self.assertEqual(self.aq.estimate_initial_capacity(villa), 6400)
        villa.population = 751
        self.assertEqual(self.aq.estimate_initial_capacity(villa), 8000)

    def test_is_attack_possible(self):
        villa = self.aq.queue[0]    # fresh village, estimate against AttackQueue.initial_capacity value (default =2400)
        lc = 'light'
        axe = 'axe'
        troops_map = {lc:25, axe:200}
        self.assertFalse(self.aq.is_attack_possible(villa, troops_map))

        troops_map = {lc:50, axe:200}   # 30 LC is enough to attack (2400 / 80)
        # returns {unit.name: units_needed}, time_on_road
        check = self.aq.is_attack_possible(villa, troops_map)
        self.assertTrue(check)
        self.assertTrue(lc in check[0])
        self.assertFalse(axe in check[0])
        self.assertEqual(check[0][lc], 30)
        # distance to 1st village in queue = 1 tile, t_on_road = 1*10*60
        self.assertEqual(check[1], 600)

        villa.remaining_capacity = 6000
        villa.last_visited = time.mktime(time.gmtime())
        villa.h_rates = [9, 9, 9]
        troops_map = {lc:30, axe:600}   # 600 is not enough due to hour/rates
        check = self.aq.is_attack_possible(villa, troops_map)
        self.assertFalse(check)
        troops_map = {lc:30, axe:700}
        check = self.aq.is_attack_possible(villa, troops_map)
        self.assertTrue(check)
        self.assertTrue(axe in check[0])
        self.assertFalse(lc in check[0])

    def test_get_next_attack_target(self):
        villa = self.aq.queue[0]
        lc = 'light'
        axe = 'axe'
        troops_map = {lc:20, axe:500}
        # get_next_attack = ((x,y), {unit.name: count}, t_on_road)
        get_next_attack = self.aq.get_next_attack_target(troops_map)
        self.assertTrue(get_next_attack) # Enough troops to loot the first village in queue
        self.assertEqual(villa.coords, get_next_attack[0])
        self.assertTrue(axe in get_next_attack[1])
        self.assertEqual(get_next_attack[1][axe], 240)
        self.assertEqual(get_next_attack[2], 1080)  # 1*18*60

        troops_map = {lc:20, axe:100}   #Not enough to loot first, should search deeper and find 'our' village
        villa = self.aq.queue[self.aq.depth]
        self.aq.queue[self.aq.depth].remaining_capacity = 1200 # Modify queue in-place
        self.aq.queue[self.aq.depth].last_visited = time.mktime(time.gmtime())
        self.aq.queue[self.aq.depth].h_rates = [1, 1, 1]
        get_next_attack = self.aq.get_next_attack_target(troops_map)
        self.assertTrue(get_next_attack)
        self.assertEqual(villa.coords, get_next_attack[0])
        self.assertTrue(lc in get_next_attack[1])
        self.assertEqual(get_next_attack[1][lc], 15)

    def test_update_villages(self):
        new_reports = self.report_builder.get_new_reports()
        self.aq.update_villages(new_reports)

        for coords, report in new_reports.items():
            in_aq_villa = self.aq.villages[coords]
            # Villages in AttackQueue.villages were updated
            self.assertEqual(in_aq_villa.last_visited, report.t_of_attack)
            self.assertEqual(in_aq_villa.mine_levels, report.mine_levels)
            self.assertEqual(in_aq_villa.remaining_capacity, report.remaining_capacity)
            # Double-check: AQ.queue also contains latest information
            in_queue_villa = [villa for villa in self.aq.queue if villa.coords == coords][0]
            self.assertEqual(in_queue_villa.last_visited, report.t_of_attack)
            self.assertEqual(in_queue_villa.mine_levels, report.mine_levels)
            self.assertEqual(in_queue_villa.remaining_capacity, report.remaining_capacity)


class TestReportBuilder(unittest.TestCase):
    """
    Tests for ReportBuilder class.
    Uses DummyRequestManager class as stub
    """
    
    def setUp(self):
        self.builder = ReportBuilder(DummyRequestManager(), Lock())
    
    def test_get_new_reports(self):
        new_reports = self.builder.get_new_reports()
        self.assertTrue(isinstance(new_reports, dict))
        self.assertEqual(len(new_reports), 3)
        for key, value in new_reports.items():
            self.assertIsInstance(key, tuple)
            self.assertIsInstance(key[0], int)
            self.assertIsInstance(key[1], int)
            self.assertIsInstance(value, AttackReport)
        
        self.assertTrue((209,309) in new_reports)
        self.assertTrue((214, 320) in new_reports)
        self.assertTrue((215, 320) in new_reports)
        
        

    
#    def test_integration_w_village(self):
#        villa = Village((200, 300), 10000, 100)
#        villa.update_stats(self.green_report)
#        self.assertEqual(self.green_report.mine_levels, villa.mine_levels)
#        self.assertEqual(self.green_report.t_of_attack, villa.last_visited)
#        self.assertEqual(self.green_report.remaining_capacity, villa.remaining_capacity)
#        self.assertEqual(self.green_report.looted_capacity, villa.looted["total"])
#        self.assertEqual(self.green_report.t_of_attack, villa.looted["per_visit"][0][0])
#        self.assertEqual(self.green_report.looted_capacity, villa.looted["per_visit"][0][1])
#
#        villa.update_stats(self.yellow_report)
#        self.assertEqual(self.yellow_report.mine_levels, villa.mine_levels)
#        self.assertEqual(self.yellow_report.t_of_attack, villa.last_visited)
#        self.assertEqual(self.yellow_report.remaining_capacity, villa.remaining_capacity)
#        total = self.green_report.looted_capacity + self.yellow_report.looted_capacity
#        self.assertEqual(total, villa.looted["total"])
#        self.assertEqual(self.yellow_report.t_of_attack, villa.looted["per_visit"][1][0])
#        self.assertEqual(self.yellow_report.looted_capacity, villa.looted["per_visit"][1][1])
        
        
        


if __name__ == '__main__':
    unittest.main()
        