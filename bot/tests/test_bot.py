    # def test_merge_sectors_data(self):
    #     sectors_data_unique = [{(1, 1): 'test11', (2, 2): 'test22'},
    #                            {(3, 3): 'test33', (4, 4): 'test44'}]
    #     expected = {(1, 1): 'test11', (2, 2): 'test22',
    #                 (3, 3): 'test33', (4, 4): 'test44'}
    #     actual = self.village_manager._merge_sectors_data(sectors_data_unique)
    #     self.assertTrue(expected, actual)
    #
    #     sectors_data_non_unique = [{(1, 1): 'test11', (2, 2): 'test22'},
    #                                {(1, 1): 'test33', (4, 4): 'test44'}]
    #     expected = {(1, 1): 'test33', (2, 2): 'test22',  (4, 4): 'test44'}
    #     actual = self.village_manager._merge_sectors_data(sectors_data_non_unique)
    #     self.assertTrue(expected, actual)
    #
    # def test_filter_distinct_centers(self):
    #     """
    #     Possible situations:
    #     1) All farming centers lie in the same sector as
    #     current attacker: expected return = [] (empty list)
    #     2) All farming centers lie in different sectors
    #     from attacker: expected return = list with all centers,
    #     current attacker not in returned list
    #     3) Some farming centers do lie in the same sector as
    #     current attacker and some centers do not. expected
    #     return: list with centers that do not lie in attacker's
    #     sector, attacker is not in returned list.
    #     Expected returned type = list of tuples, where each tuple
    #     is (x, y) coordinates
    #     """
    #     current_attacker = (1, 1)
    #     centers = [((2, 2), 'a'), ((3, 3), 'b'), ((4, 4), 'c'), ((5, 5), 'd')]
    #     # some non-centers point added for plausibility
    #     all_in_one_data = [{(1, 1): '', (2, 2): '', (3, 3): '',
    #                         (4, 4): '', (5, 5): ''}, {(6, 6): '', (7, 7): ''}]
    #     distinct_centers = self.village_manager._filter_distinct_centers(
    #         current_attacker, centers, all_in_one_data)
    #     self.assertEqual(distinct_centers, [])
    #
    #     all_in_separate = [{(1, 1): '', (10, 10): ''}, {(2, 2): '', (3, 3): ''},
    #                        {(4, 4): '', (8, 8): '', (10, 10): '', (5, 5): ''}]
    #     distinct_centers = self.village_manager._filter_distinct_centers(
    #         current_attacker, centers, all_in_separate)
    #     self.assertCountEqual(distinct_centers, centers)
    #
    #     in_same_and_separate = [{(1, 1): '', (2, 2): '', (3, 3): ''},
    #                             {(4, 4): '', (7, 7): '', (9, 9): ''},
    #                             {(5, 5): '', (6, 6): ''}]
    #     distinct_centers = self.village_manager._filter_distinct_centers(
    #         current_attacker, centers, in_same_and_separate)
    #     self.assertCountEqual(distinct_centers, [((4, 4), 'c'), ((5, 5), 'd')])
    #
    # def test_get_map_data(self):
    #     # refresh calls to request_manager:
    #     self.village_manager.request_manager.method_calls = []
    #     # 1 case: ._get_map_data is called with empty list
    #     # of farming centers. expected: return value = empty dict,
    #     # no calls to request_manager were performed
    #     map_data = self.village_manager._get_map_data([], map_depth=10)
    #     self.assertEqual(map_data, {})
    #     self.assertEqual(len(self.village_manager.request_manager.method_calls), 0)
    #     # 2 case: ._get_map_data is called with 2 farming
    #     # centers, that belong to the same sector & with map_depth=1
    #     # expected: ._get_map_overview method is called once (for 1st
    #     # farming center); no calls to MapMath.get_area_corners method;
    #     # return value = merged sectors data.
    #     with patch('bot.libs.village_management.MapMath', autospec=True) as map_math:
    #         distinct_centers = []
    #         distinct_centers.append(((1, 1), 1))  # ((x, y), id)
    #         distinct_centers.append(((2, 2), 2))
    #         # set return value for .collect_sectors_data of map_parser,
    #         # so both centers are in the same sector
    #         self.village_manager.map_parser.collect_sector_data.return_value = \
    #             [{(1, 1): ['1001'], (2, 2): ['1002'], (3, 3): ['1003']},
    #              {(4, 4): ['1004'], (5, 5): ['1005']},
    #              {(8, 8): ['1008'], (10, 10): ['1010'], (6, 6): ['1006']},
    #              {(0, 0): ['10000'], (0, 1000): ['10001'], (1000, 0): ['10002'],
    #               (1000, 1000): ['10003']}]
    #         expected_return_value = {(1, 1): ['1001'], (2, 2): ['1002'],
    #                                  (3, 3): ['1003'], (4, 4): ['1004'],
    #                                  (5, 5): ['1005'], (6, 6): ['1006'],
    #                                  (8, 8): ['1008'], (10, 10): ['1010'],
    #                                  (0, 0): ['10000'], (0, 1000): ['10001'],
    #                                  (1000, 0): ['10002'], (1000, 1000): ['10003']}
    #         map_data = self.village_manager._get_map_data(distinct_centers, map_depth=1)
    #         self.assertEqual(map_data, expected_return_value)
    #         calls_to_rm = self.village_manager.request_manager.method_calls
    #         self.assertEqual(len(calls_to_rm), 1)
    #         self.assertIn(call.get_map_overview(1, 1, 1), calls_to_rm)
    #         # refresh calls to request_manager:
    #         self.village_manager.request_manager.method_calls = []
    #         # 3 case: 2 farming centers (same sector), map_depth=2.
    #         # expected: _get_map_overview is called 5 times (center +
    #         # 4 area corners. return value = merged sectors data
    #         map_math.get_area_corners.return_value = [(0, 0), (0, 1000),
    #                                                   (1000, 0), (1000, 1000)]
    #         map_data = self.village_manager._get_map_data(distinct_centers, map_depth=2)
    #         self.assertEqual(map_data, expected_return_value)
    #         calls_to_rm = self.village_manager.request_manager.method_calls
    #         self.assertEqual(len(calls_to_rm), 5)
    #         self.assertIn(call.get_map_overview(1, 1, 1), calls_to_rm)
    #         self.assertIn(call.get_map_overview(10000, 0, 0), calls_to_rm)
    #         self.assertIn(call.get_map_overview(10001, 0, 1000), calls_to_rm)
    #         self.assertIn(call.get_map_overview(10002, 1000, 0), calls_to_rm)
    #         self.assertIn(call.get_map_overview(10003, 1000, 1000), calls_to_rm)
    #         # refresh calls to request_manager:
    #         self.village_manager.request_manager.method_calls = []
    #         # 4 case: 2 farming centers in distinct sectors, map_depth=2.
    #         # expected: _get_map_overview is called 10 times (each center &
    #         # 4 area corners for each center. return value = merged sectors data
    #         self.village_manager.map_parser.collect_sector_data.return_value = \
    #             [{(1, 1): ['1001'], (3, 3): ['1003'], (1000, 1000): ['10003']},
    #              {(2, 2): ['1002'], (4, 4): ['1004'], (5, 5): ['1005']},
    #              {(8, 8): ['1008'], (10, 10): ['1010'], (6, 6): ['1006']},
    #              {(0, 0): ['10000'], (0, 1000): ['10001'], (1000, 0): ['10002']}]
    #         map_data = self.village_manager._get_map_data(distinct_centers, map_depth=2)
    #         self.assertEqual(map_data, expected_return_value)
    #         calls_to_rm = self.village_manager.request_manager.method_calls
    #         expected_calls = [call.get_map_overview(1, 1, 1),
    #                           call.get_map_overview(2, 2, 2),
    #                           call.get_map_overview(10000, 0, 0),
    #                           call.get_map_overview(10000, 0, 0),
    #                           call.get_map_overview(10001, 0, 1000),
    #                           call.get_map_overview(10001, 0, 1000),
    #                           call.get_map_overview(10002, 1000, 0),
    #                           call.get_map_overview(10002, 1000, 0),
    #                           call.get_map_overview(10003, 1000, 1000),
    #                           call.get_map_overview(10003, 1000, 1000)]
    #         self.assertCountEqual(expected_calls, calls_to_rm)
