import time
import unittest
import shelve
from map_management import Map
from map_management import Village
from attack_management import *
from data_management import *
from request_manager import DummyRequestManager



class TestAttackQueue(unittest.TestCase):

    def setUp(self):
        self.aq = AttackQueue(211, 305, DummyRequestManager(), mapfile='test_data/testmap')
        self.report_builder = ReportBuilder(DummyRequestManager())

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
        fresh_village = Village((100, 100), 100)
        self.assertTrue(self.aq.is_ready_for_farm(fresh_village))

    def test_estimate_arrival(self):
        distance = 10
        speed = 10
        time_on_road = distance*speed*60
        expected_arrival = time.mktime(time.gmtime()) + time_on_road
        self.assertAlmostEqual(expected_arrival, self.aq.estimate_arrival(distance, speed))

    def test_estimate_troops_needed(self):
        lc = LightCavalry()
        self.assertEqual(self.aq.estimate_troops_needed(lc), 30)
        self.assertEqual(self.aq.estimate_troops_needed(lc, 4800), 60)

    def test_is_attack_possible(self):
        villa = self.aq.queue[0]    # fresh village, estimate against AttackQueue.initial_capacity value (default =2400)
        lc = LightCavalry()
        axe = Axeman()
        troops_map = {lc:25, axe:200}
        self.assertFalse(self.aq.is_attack_possible(villa, troops_map))

        troops_map = {lc:30, axe:200}   # 30 LC is enough to attack (2400 / 80)
        units_needed = self.aq.is_attack_possible(villa, troops_map)
        self.assertTrue(units_needed)
        self.assertTrue(lc in units_needed)
        self.assertFalse(axe in units_needed)
        self.assertEqual(units_needed[lc], 30)

        villa.remaining_capacity = 6000
        villa.last_visited = time.mktime(time.gmtime())
        villa.h_rates = [9, 9, 9]
        troops_map = {lc:30, axe:600}   # 600 is not enough due to hour/rates
        units_needed = self.aq.is_attack_possible(villa, troops_map)
        self.assertFalse(units_needed)
        troops_map = {lc:30, axe:700}
        units_needed = self.aq.is_attack_possible(villa, troops_map)
        self.assertTrue(units_needed)
        self.assertTrue(axe in units_needed)
        self.assertFalse(lc in units_needed)

    def test_get_next_attack_target(self):
        villa = self.aq.queue[0]
        lc = LightCavalry()
        axe = Axeman()
        troops_map = {lc:20, axe:310}
        get_attack = self.aq.get_next_attack_target(troops_map)
        self.assertTrue(get_attack) # Enough troops to loot the first village in queue
        self.assertEqual(villa.coords, get_attack[0])
        self.assertTrue(axe in get_attack[1])
        self.assertEqual(get_attack[1][axe], 240)

        troops_map = {lc:20, axe:100}   #Not enough to loot first, should search deeper and find 'our' village
        villa = self.aq.queue[self.aq.depth]
        self.aq.queue[self.aq.depth].remaining_capacity = 1200 # Modify queue in-place
        self.aq.queue[self.aq.depth].last_visited = time.mktime(time.gmtime())
        self.aq.queue[self.aq.depth].h_rates = [1, 1, 1]
        get_attack = self.aq.get_next_attack_target(troops_map)
        self.assertTrue(get_attack)
        self.assertEqual(villa.coords, get_attack[0])
        self.assertTrue(lc in get_attack[1])
        self.assertEqual(get_attack[1][lc], 15)

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


class TestMap(unittest.TestCase):
    
    def setUp(self):
        self.mapfile = 'test_data/testmap'
        self.build_dummy_villages()
        self.build_valid_villages()
        self.map = Map(211, 305, DummyRequestManager(), depth=3, mapfile=self.mapfile)        
    
    def build_dummy_villages(self):
        """Create and save villages that should be filtered
        out upon Map initialization (will not be found in map-HTML)
        """
        villa_min_min = Village((100, 100), 1)
        villa_min_max = Village((100, 1000), 2)
        villa_max_min = Village((1000, 100), 3)
        villa_max_max = Village((1000, 1000), 4)
        self.dummy_villages = (villa_min_min, villa_min_max,
                   villa_max_min, villa_max_max)
        self.save_villages(self.dummy_villages)
           
    def build_valid_villages(self):
        """Create and save villages that exist in map-HTML.
        These villages should retain their state in Map.villages
        """
        valid_bonus = Village((218, 305), 133228)
        valid_bonus.mine_levels = (12, 12, 12)  # Add some state for valid villages
        valid_bonus.remaining_capacity = 4000   # to check that it will be retained
        valid_barb = Village((218, 307), 125319)
        valid_barb.mine_levels = (13, 13, 13)
        valid_barb.remaining_capacity = 2000
        self.valid_villages = (valid_bonus, valid_barb)
        self.save_villages(self.valid_villages)
    
    def save_villages(self, villages):
        f = shelve.open(self.mapfile)
        if 'villages' in f:
            temp_villages = f['villages']
        else:
            temp_villages = {}        
        for villa in villages:
            temp_villages[villa.coords] = villa
        f['villages'] = temp_villages
        f.close()
        
    def test_base_workability(self):
        self.assertEqual(self.mapfile, self.map.mapfile)
        self.assertTrue(len(self.map.villages) > 0)
        for coords, villa in self.map.villages.items():   # {(x,y): {"village":Village, "distance":distance}, ...}
            self.assertIsInstance(coords, tuple)
            self.assertTrue(isinstance(coords[0], int) and isinstance(coords[1], int))
            self.assertIsInstance(villa, Village)
            self.assertIsInstance(villa.dist_from_base, float)
    
    def test_build_villages(self):
        """Tests final state of self.map.villages and
        of local mapfile.
        """
        in_test_map = [Village((211, 306), 135083), 
                       Village((200, 306), 137156),
                       Village((212, 289), 136936),
                       Village((212, 318), 120821),
                       Village((225, 304), 128693)]
        not_in_test_map = [(211, 307), (210, 305),
                           (227, 309), (217, 324)]
        for villa in in_test_map:
            self.assertTrue(villa.coords in self.map.villages)
            self.assertEqual(villa.id, self.map.villages[villa.coords].id)
        for coords in not_in_test_map:
            self.assertTrue(coords not in self.map.villages)
        f = shelve.open(self.mapfile)
        for dummy in self.dummy_villages:
            self.assertTrue(dummy.coords not in self.map.villages)  # Dummies were no included
            self.assertTrue(dummy.coords not in f['villages'])  # Dummies were deleted upon Map init
        for valid_villa in self.valid_villages:
            coords = valid_villa.coords
            self.assertTrue(coords in self.map.villages)
            self.assertTrue(coords in f['villages'])
            # Check state of valid villages in self.map.villages
            in_map_valid_villa = self.map.villages[coords]
            self.assertEqual(valid_villa.mine_levels, in_map_valid_villa.mine_levels)
            self.assertEqual(valid_villa.remaining_capacity, in_map_valid_villa.remaining_capacity)
        f.close()
    
    def test_update_villages(self):
        valid_copies = {}
        for villa in self.valid_villages:
            coords = villa.coords
            valid_copies[coords] = villa
            valid_copies[coords].mine_levels = (1, 1, 1)
            valid_copies[coords].remaining_capacity = 1000
        self.map.update_villages(valid_copies)
        f = shelve.open(self.mapfile)
        for coords, villa in valid_copies.items():
            self.assertTrue(coords in f['villages'])
            self.assertEqual(villa.mine_levels, f['villages'][coords].mine_levels)
            self.assertEqual(villa.remaining_capacity, f['villages'][coords].remaining_capacity)
            self.assertTrue(coords in self.map.villages)
            self.assertEqual(villa.mine_levels, self.map.villages[coords].mine_levels)
            self.assertEqual(villa.remaining_capacity, self.map.villages[coords].remaining_capacity)
        f.close()

    def test_get_sector_corners(self):
        """Inject dummies into Map.villages. Dummies coordinates
        are certainly the corner points
        """
        dummy_coords = [x.coords for x in self.dummy_villages]
        all_coords = [coords for coords in self.map.villages.keys()]
        all_coords.extend(dummy_coords)
        corners = self.map.get_sector_corners(all_coords)
        self.assertEqual(len(corners), 4)
        for dummy in self.dummy_villages:
            self.assertTrue(dummy.coords in corners)
    
    def test_is_valid(self):
        non_valid = [['110479', 7, 'Claus laaan', '952', '10155826', '100'],
                     ['128694', 18, 'Bonus village', '313', 'M140', '100', ['100% higher clay production', 'bonus/stone.png']]
                     ]
        valid = [['129120', 4, 0, '138', '0', '100'], 
                 ['129795', 16, 'Bonus village', '247', '0', '100', ['30% more resources are produced (all resource types)', 'bonus/all.png']]
                 ]
        for villa_data in non_valid:
            self.assertFalse(self.map.is_valid(villa_data))
        for villa_data in valid:
            self.assertTrue(self.map.is_valid(villa_data))
            
    def test_get_village(self):
        villa_data = ['129795', 16, 'Bonus village', '247', '0', '100', 
                        ['30% more resources are produced (all resource types)', 'bonus/all.png']]
        villa_coords = (100, 100)
        villa = self.map.get_village(villa_coords, villa_data, 100)
        self.assertEqual(villa.coords, villa_coords)
        self.assertEqual(villa.bonus, villa_data[6][0])
        self.assertEqual(villa.dist_from_base, 100)
    
    def test_calculate_distance(self):
        self.assertEqual(self.map.calculate_distance((100, 100)), 233.12)
    
    def test_get_villages_in_range(self):
        in_range = self.map.get_villages_in_range(6)
        self.assertTrue((215, 301) in in_range)
        self.assertTrue((211, 311) in in_range)
        self.assertFalse((205, 304) in in_range)
        self.assertFalse((218, 305) in in_range)
        in_range = self.map.get_villages_in_range(15)
        self.assertTrue((225, 304) in in_range)
        self.assertTrue((212, 318) in in_range)
        self.assertFalse((212, 289) in in_range)
        self.assertFalse((196, 306) in in_range)
        

class TestReportBuilder(unittest.TestCase):
    """
    Tests for ReportBuilder class.
    Uses DummyRequestManager class as stub
    """
    
    def setUp(self):
        self.builder = ReportBuilder(DummyRequestManager())
    
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

    def test_invalid_report(self):
        with open(r'test_html/single_report_blue.html') as f:
            s_recon_report = f.read()
            recon_report = AttackReport(s_recon_report)
            self.assertFalse(recon_report.is_valid_report)
        with open(r'test_html/single_report_red.html') as f:
            s_red_report = f.read()
            red_report = AttackReport(s_red_report)
            self.assertFalse(red_report.is_valid_report)
        with open(r'test_html/single_report_support.html') as f:
            s_support_report = f.read()
            support_report = AttackReport(s_support_report)
            self.assertFalse(support_report.is_valid_report)

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
        self.assertIsInstance(rates, list)
        self.assertIsInstance(rates[0], int)
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

    def test_is_fresh_meat(self):
        fresh_villa = Village((100, 100), 100)
        self.assertTrue(fresh_villa.is_fresh_meat())
        fresh_villa.last_visited = 1
        self.assertFalse(fresh_villa.is_fresh_meat())

    def test_passes_threshold(self):
        fresh_villa = Village((100, 100), 100)
        threshold = 2400
        fresh_villa.remaining_capacity = threshold - 1
        self.assertFalse(fresh_villa.passes_threshold(threshold))
        fresh_villa.remaining_capacity = threshold + 1
        self.assertTrue(fresh_villa.passes_threshold(threshold))

    def test_finished_rest(self):
        fresh_villa = Village((100, 100), 100)
        rest = 3600
        fresh_villa.last_visited = time.mktime(time.gmtime()) - (rest - 100)
        self.assertFalse(fresh_villa.finished_rest(rest))
        fresh_villa.last_visited = time.mktime(time.gmtime()) - (rest + 100)
        self.assertTrue(fresh_villa.finished_rest(rest))
        
if __name__ == '__main__':
    unittest.main()
        