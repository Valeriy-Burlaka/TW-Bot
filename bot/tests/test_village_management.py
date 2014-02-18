


class TestPlayerVillage(unittest.TestCase):

    def setUp(self):
        with open('test_html/village_overview_test_pv_initial.html') as f:
            self.overview_html_init = f.read()
        with open('test_html/village_overview_test_pv_updated.html') as f:
            self.overview_html_updated = f.read()
        with open('test_html/train_screen.html') as f:
            self.train_html = f.read()

    def test_initial_troops(self):
        pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, False, 4)
        correct_troops_to_use = ['axe', 'spy', 'light', 'marcher', 'heavy']
        self.assertEqual(correct_troops_to_use, pv.troops_to_use)
        self.assertEqual(pv.troops_count['axe'], 33)
        self.assertEqual(pv.troops_count['spy'], 395)
        self.assertEqual(pv.troops_count['light'], 9)
        self.assertEqual(pv.troops_count['marcher'], 18)
        self.assertEqual(pv.troops_count['heavy'], 129)
        pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, True, 4)
        correct_troops_to_use = ['spear', 'sword', 'archer', 'axe', 'spy', 'light', 'marcher', 'heavy']
        self.assertEqual(correct_troops_to_use, pv.troops_to_use)
        self.assertEqual(pv.troops_count['axe'], 33)
        self.assertEqual(pv.troops_count['spy'], 395)
        self.assertEqual(pv.troops_count['light'], 9)
        self.assertEqual(pv.troops_count['marcher'], 18)
        self.assertEqual(pv.troops_count['heavy'], 129)
        self.assertEqual(pv.troops_count['spear'], 370)
        self.assertEqual(pv.troops_count['sword'], 458)
        self.assertEqual(pv.troops_count['archer'], 117)

    def test_set_preferred_farm_radius(self):
        pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, True, 4)
        self.assertEqual(pv.radius, 21.87)
        pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, False, 3)
        self.assertEqual(pv.radius, 17.05)

    def test_update_troops_count(self):
        pv = PlayerVillage(127591, (211, 305), 'Test', self.train_html, True, 4)
        with open('test_html/train_screen_update.html') as f:
            train_html_updated = f.read()
        pv.update_troops_count(train_screen_html=train_html_updated)
        self.assertEqual(pv.troops_count['axe'], 95)
        self.assertEqual(pv.troops_count['spy'], 393)
        self.assertEqual(pv.troops_count['light'], 0)
        self.assertEqual(pv.troops_count['marcher'], 36)
        self.assertEqual(pv.troops_count['heavy'], 298)
        self.assertEqual(pv.troops_count['spear'], 173)
        self.assertEqual(pv.troops_count['sword'], 200)
        self.assertEqual(pv.troops_count['archer'], 146)
        troops_sent = {'spear': 100, 'axe': 95, 'heavy': 10, 'spy': 2}
        pv.update_troops_count(troops_sent=troops_sent)
        self.assertEqual(pv.troops_count['axe'], 0)
        self.assertEqual(pv.troops_count['spy'], 391)
        self.assertEqual(pv.troops_count['light'], 0)
        self.assertEqual(pv.troops_count['marcher'], 36)
        self.assertEqual(pv.troops_count['heavy'], 288)
        self.assertEqual(pv.troops_count['spear'], 73)
        self.assertEqual(pv.troops_count['sword'], 200)
        self.assertEqual(pv.troops_count['archer'], 146)


class TestVillage(unittest.TestCase):
    """
    Tests for bot's Village class. Uses stub object
    instead of real AttackReport for .test_update_stats()
    method.
    """

    def setUp(self):
        self.barb = Village((200, 300), 10000, 100)
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

        villa = Village((100, 200), 10005, 200)
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
        fresh_villa = Village((100, 100), 100, 200)
        self.assertTrue(fresh_villa.is_fresh_meat())
        fresh_villa.last_visited = 1
        self.assertFalse(fresh_villa.is_fresh_meat())

    def test_passes_threshold(self):
        fresh_villa = Village((100, 100), 100, 200)
        threshold = 2400
        fresh_villa.remaining_capacity = threshold - 1
        self.assertFalse(fresh_villa.passes_threshold(threshold))
        fresh_villa.remaining_capacity = threshold + 1
        self.assertTrue(fresh_villa.passes_threshold(threshold))

    def test_finished_rest(self):
        fresh_villa = Village((100, 100), 100, 200)
        rest = 3600
        fresh_villa.last_visited = time.mktime(time.gmtime()) - (rest - 100)
        self.assertFalse(fresh_villa.finished_rest(rest))
        fresh_villa.last_visited = time.mktime(time.gmtime()) - (rest + 100)
        self.assertTrue(fresh_villa.finished_rest(rest))

   #
   # def test_get_village(self):
   #      villa_data = ['129795', 16, 'Bonus village', '247', '0', '100',
   #                      ['30% more resources are produced (all resource types)', 'bonus/all.png']]
   #      villa_coords = (100, 100)
   #      villa = self.map.get_village(villa_coords, villa_data, 100)
   #      self.assertEqual(villa.coords, villa_coords)
   #      self.assertEqual(villa.bonus, villa_data[6][0])
   #      self.assertEqual(villa.dist_from_base, 100)


    # def test_is_valid(self):
    #     non_valid = [['110479', 7, 'Claus laaan', '952', '10155826', '100'],
    #                  ['128694', 18, 'Bonus village', '313', 'M140', '100', ['100% higher clay production', 'bonus/stone.png']]
    #                  ]
    #     valid = [['129120', 4, 0, '138', '0', '100'],
    #              ['129795', 16, 'Bonus village', '247', '0', '100', ['30% more resources are produced (all resource types)', 'bonus/all.png']]
    #              ]
    #     for villa_data in non_valid:
    #         self.assertFalse(self.map.is_valid(villa_data))
    #     for villa_data in valid:
    #         self.assertTrue(self.map.is_valid(villa_data))