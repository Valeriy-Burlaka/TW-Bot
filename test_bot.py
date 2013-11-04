import time
import unittest
from bot import *


class TestAttackReport(unittest.TestCase):
    """
    Tests for bot's AttackReport class.
    Uses hardcoded paths to HTML report files.
    """
    
    def setUp(self):
        with open(r'test_html/single_report_green.html') as f:
            s_green_report = f.read()
        with open(r'test_html/single_report_yellow.html') as f:
            s_yellow_report = f.read()
        self.green_report = AttackReport(s_green_report)
        self.yellow_report = AttackReport(s_yellow_report)
    
    def test_set_status(self):
        self.assertEqual(self.green_report.status, 'green')
        self.assertEqual(self.yellow_report.status, 'yellow')
   
    def test_set_t_of_attack(self):
        # 'green' time: "Nov 03, 2013  14:01:57"
        struct_t = time.struct_time((2013, 11, 3, 14, 1, 57, 0, 0, 0))
        green_time = round(time.mktime(struct_t))
        self.assertEqual(self.green_report.t_of_attack, green_time)
        # 'yellow' time: "Nov 02, 2013  17:49:01"
        struct_t = time.struct_time((2013, 11, 2, 17, 49, 1, 0, 0, 0))
        yellow_time = round(time.mktime(struct_t))
        self.assertEqual(self.yellow_report.t_of_attack, yellow_time)
        
    def test_set_mines_level(self):
        green_levels = [9, 1, 2]
        yellow_levels = [7, 4, 5]
        self.assertEqual(self.green_report.mine_levels, green_levels)
        self.assertEqual(self.yellow_report.mine_levels, yellow_levels) 
    
    def test_set_capacity(self):
        green_loot = 2400
        green_left = 1686
        yellow_loot = 3120
        yellow_left = 1656
        self.assertEqual(self.green_report.looted_capacity, green_loot)
        self.assertEqual(self.green_report.remaining_capacity, green_left)
        self.assertEqual(self.yellow_report.looted_capacity, yellow_loot)
        self.assertEqual(self.yellow_report.remaining_capacity, yellow_left)
    
    def test_integration_w_village(self):
        villa = Village((200, 300), 10000)
        villa.update_stats(self.green_report)
        self.assertEqual(self.green_report.mine_levels, villa.mine_levels)
        self.assertEqual(self.green_report.t_of_attack, villa.last_visited)
        self.assertEqual(self.green_report.remaining_capacity, villa.remaining_capacity)
        self.assertEqual(self.green_report.looted_capacity, villa.looted["total"])
        self.assertEqual(self.green_report.t_of_attack, villa.looted["per_visit"][0][0])
        self.assertEqual(self.green_report.looted_capacity, villa.looted["per_visit"][0][1])
        
        villa.update_stats(self.yellow_report)
        self.assertEqual(self.yellow_report.mine_levels, villa.mine_levels)
        self.assertEqual(self.yellow_report.t_of_attack, villa.last_visited)
        self.assertEqual(self.yellow_report.remaining_capacity, villa.remaining_capacity)
        total = self.green_report.looted_capacity + self.yellow_report.looted_capacity
        self.assertEqual(total, villa.looted["total"])
        self.assertEqual(self.yellow_report.t_of_attack, villa.looted["per_visit"][1][0])
        self.assertEqual(self.yellow_report.looted_capacity, villa.looted["per_visit"][1][1])
        
        
        
class TestVillage(unittest.TestCase):
    """
    Tests for bot's Village class. Uses stub object
    instead of real AttackReport for .test_update_stats()
    method.
    """
    
    def setUp(self):
        self.barb = Village((200, 300), 10000)
        self.bonus_all = Village((100, 100), 10001, 
                                "30% more resources are produced (all resource type)")
        self.bonus_wood = Village((0, 0), 10002,
                                 "100% higher wood production")
        self.bonus_clay = Village((0, 100), 10003,
                                 "100% higher clay production")
        self.bonus_iron = Village((100, 0), 10004,
                                 "100% higher iron production")
    
    def test_get_rates_table(self):
        rates = self.barb.get_rates_table()
        self.assertTrue(isinstance(rates, list))
        self.assertTrue(isinstance(rates[0], int))
        self.assertEqual(len(rates), 31)
    
    def test_set_h_rates(self):
        self.barb.mine_levels = [10, 11, 12]
        self.barb.set_h_rates()
        self.assertTrue(self.barb.h_rates)
        self.assertEqual(self.barb.h_rates[0], 117)
        self.assertEqual(self.barb.h_rates[1], 136)
        self.assertEqual(self.barb.h_rates[2], 158)
        
        self.bonus_all.mine_levels = [9, 9, 9]
        self.bonus_all.set_h_rates()
        self.assertTrue(self.bonus_all.h_rates)
        self.assertEqual(self.bonus_all.h_rates[0], 133)
        self.assertEqual(self.bonus_all.h_rates[1], 133)
        self.assertEqual(self.bonus_all.h_rates[2], 133)
        
        self.bonus_wood.mine_levels = [1, 2, 3]
        self.bonus_wood.set_h_rates()
        self.assertTrue(self.bonus_wood.h_rates)
        self.assertEqual(self.bonus_wood.h_rates[0], 60)
        self.assertEqual(self.bonus_wood.h_rates[1], 35)
        self.assertEqual(self.bonus_wood.h_rates[2], 41)
        
        self.bonus_clay.mine_levels = [4, 5, 6]
        self.bonus_clay.set_h_rates()
        self.assertTrue(self.bonus_clay.h_rates)
        self.assertEqual(self.bonus_clay.h_rates[0], 47)
        self.assertEqual(self.bonus_clay.h_rates[1], 110)
        self.assertEqual(self.bonus_clay.h_rates[2], 64)
        
        self.bonus_iron.mine_levels = [20, 15, 8]
        self.bonus_iron.set_h_rates()
        self.assertTrue(self.bonus_iron.h_rates)
        self.assertEqual(self.bonus_iron.h_rates[0], 530)
        self.assertEqual(self.bonus_iron.h_rates[1], 249)
        self.assertEqual(self.bonus_iron.h_rates[2], 172)
        
    def test_estimate_capacity(self):
        self.barb.mine_levels = [20, 20, 20]
        self.barb.set_h_rates()
        self.barb.last_visited = 10000
        self.barb.remaining_capacity = 2000
        self.assertEqual(self.barb.estimate_capacity(17200), 5180)
        
        self.barb.remaining_capacity = 0
        self.assertEqual(self.barb.estimate_capacity(17200), 3180)
        
        self.barb.last_visited = None
        three_h_production = sum(x * 3 for x in self.barb.h_rates)
        t = time.mktime(time.gmtime())
        t_to_arrival = t + 10800
        self.assertEqual(self.barb.estimate_capacity(t_to_arrival), three_h_production)
        
    def test_update_stats(self):
        class dummy_report:
            pass
        report = dummy_report()
        report.t_of_attack = 10000
        report.mine_levels = [13, 14, 15]
        report.remaining_capacity = 3000
        report.looted_capacity = 4000
        
        villa = Village((100, 200), 10005)
        villa.update_stats(report)
        self.assertEqual(villa.last_visited, 10000)
        self.assertEqual(villa.mine_levels, [13, 14, 15])
        self.assertEqual(villa.h_rates, [184, 214, 249])
        self.assertEqual(villa.remaining_capacity, 3000)
        self.assertEqual(villa.looted["total"], 4000)
        
        report = dummy_report()
        report.t_of_attack = 20000
        report.mine_levels = [17, 18, 19]
        report.remaining_capacity = 0
        report.looted_capacity = 7000
        
        villa.update_stats(report)
        self.assertEqual(villa.last_visited, 20000)
        self.assertEqual(villa.mine_levels, [17, 18, 19])
        self.assertEqual(villa.h_rates, [337, 391, 455])
        self.assertEqual(villa.remaining_capacity, 0)
        self.assertEqual(villa.looted["total"], 11000)
        self.assertEqual(len(villa.looted["per_visit"]), 2)
        self.assertEqual(villa.looted["per_visit"][-1][0], villa.last_visited)
        self.assertEqual(villa.looted["per_visit"][-1][1], report.looted_capacity)
        
        

        
if __name__ == '__main__':
    unittest.main()
        