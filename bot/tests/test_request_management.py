import unittest
import os
import logging

import settings
from bot.app import locale
from bot.libs.request_management import SafeOpener


logging.basicConfig(level=logging.CRITICAL)


class TestSafeOpener(unittest.TestCase):

    def setUp(self):
        self.opener = SafeOpener(host='host', cookies={}, locale=None,
                                 con_attempts=5, reconnect=True, username='name',
                                 password='pass', antigate_key='key')
        self.data_path = os.path.join(settings.TEST_DATA_FOLDER, 'html', 'misc')

    def test_check_if_session_expire(self):
        self.opener.locale = locale.LOCALE["en"]

        filename = os.path.join(self.data_path, 'en_session_expired.html')
        with open(filename) as f:
            test_data = f.read()
        check = self.opener._check_if_session_expire(test_data)
        self.assertTrue(check)

        filename = os.path.join(self.data_path, 'en_session_expired-2.html')
        with open(filename) as f:
            test_data = f.read()
        check = self.opener._check_if_session_expire(test_data)
        self.assertTrue(check)

        filename = os.path.join(self.data_path, 'us_session_expired_screen.html')
        with open(filename) as f:
            test_data = f.read()
        check = self.opener._check_if_session_expire(test_data)
        self.assertTrue(check)

        filename = os.path.join(self.data_path, 'world_settings.html')
        with open(filename) as f:
            test_data = f.read()
        check = self.opener._check_if_session_expire(test_data)
        self.assertFalse(check)

        filename = os.path.join(self.data_path, 'fr_session_expired_screen.html')
        with open(filename) as f:
            test_data = f.read()
        self.opener.locale = locale.LOCALE["fr"]
        check = self.opener._check_if_session_expire(test_data)
        self.assertTrue(check)

    def test_check_if_captcha_spawned(self):
        self.opener.locale = locale.LOCALE["en"]

        filename = os.path.join(self.data_path, 'en_captcha_on_small_page.html')
        with open(filename) as f:
            test_data = f.read()
        expected_url = 'http://{host}/human.php?' \
                       's=d775cf97c86e'.format(host=self.opener.host)
        check = self.opener._check_if_captcha_spawned(test_data)
        self.assertEqual(check, expected_url)

        filename = os.path.join(self.data_path, 'en_report_page_with_captcha.html')
        with open(filename) as f:
            test_data = f.read()
        expected_url = 'http://{host}/human.php?' \
                       's=afef3a5b97df&small'.format(host=self.opener.host)
        check = self.opener._check_if_captcha_spawned(test_data)
        self.assertEqual(check, expected_url)

        self.opener.locale = locale.LOCALE["fr"]

        filename = os.path.join(self.data_path, 'fr_captcha_small.html')
        with open(filename) as f:
            test_data = f.read()
        expected_url = 'http://{host}/human.php?' \
                       's=243efdbc3da1&small'.format(host=self.opener.host)
        check = self.opener._check_if_captcha_spawned(test_data)
        self.assertEqual(check, expected_url)
