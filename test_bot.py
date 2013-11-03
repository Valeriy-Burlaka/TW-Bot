import time
import unittest
from bot import *


class TestVillage(unittest.TestCase):
    """
    Tests for bot's Village class
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
        t = time.mktime(time.localtime())
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
        