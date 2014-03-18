# import unittest
# import os
#
# import settings
# from bot.libs.common_tools import AntigateWrapper
#
#
# class TestAntigateWrapper(unittest.TestCase):
#
#     def setUp(self):
#         self.antigate = AntigateWrapper(key=settings.ANTIGATE_KEY)
#         self.test_data_path = os.path.join(settings.TEST_DATA_FOLDER, 'img')
#
#     def test_get_captcha_anwser(self):
#         filename = os.path.join(self.test_data_path, 'human_784463.png')
#         with open(filename, 'rb') as f:
#             img_bytes = f.read()
#         anwser = self.antigate.get_captcha_answer(img_bytes)
#         self.assertEqual(anwser, '784463')

