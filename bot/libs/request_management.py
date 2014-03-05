import sys
import re
import random
import time
import struct
import logging
import traceback
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

import requests

from bot.libs.common_tools import AutoLogin, AntigateWrapper


class SessionExpiredError(Exception):
    """
    Exception for the case if Bot is not asked
    to automatically re-connect when session expires.
    """
    pass


class TooManyConnectionAttempts(Exception):
    """
    Raised when SafeOpener has exceeded connection attempts.
    """
    pass


class RequestManager:

    def __init__(self, host, initial_cookies, main_id, con_attempts=3,
                 reconnect=False, username=None, password=None, antigate_key=None):
        self.safe_opener = SafeOpener(host, initial_cookies, con_attempts,
                           reconnect, username, password, antigate_key)
        self.data_provider = RequestDataProvider(host, main_id)

    def __getattr__(self, name):
        def call_wrapper(*args, **kwargs):
            if not hasattr(self.data_provider, name):
                raise NotImplementedError("This method is not implemented yet!")
            else:
                request_data = getattr(self.data_provider, name)(**kwargs)
                result = self.safe_opener.send_request(request_data)
                return result

        return call_wrapper


class RequestDataProvider:

    def __init__(self, host, global_id):
        self.host = host
        self.global_id = global_id

    def get_map_overview(self, x, y, village_id):
        url = 'http://{host}/game.php?village={id}&x={x}&y={y}&' \
              'screen=map'.format(host=self.host,
                                  id=village_id,
                                  x=x,
                                  y=y)
        headers = self._get_default_headers(referer=url)
        data = {'url': url, 'headers': headers}
        return data

    def get_overviews_screen(self):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=overview_villages&mode=combined'.format(host=self.host,
                                                              id=self.global_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=overview'.format(host=self.host,
                                           id=self.global_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_village_overview(self, village_id):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=overview'.format(host=self.host, id=village_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=overview_villages'.format(host=self.host,
                                                    id=village_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_train_screen(self, village_id):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=train'.format(host=self.host, id=village_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=overview'.format(host=self.host, id=village_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_rally_overview(self, village_id):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=place'.format(host=self.host, id=village_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=overview'.format(host=self.host, id=village_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_reports_page(self, from_page):
        url = 'http://{host}/game.php?village={id}&mode=all&' \
              'from={page}&screen=report'.format(host=self.host,
                                                 id=self.global_id,
                                                 page=from_page)
        headers = self._get_default_headers(referer=url)
        data = {'url': url, 'headers': headers}
        return data

    def get_report(self, url):
        url = 'http://{host}{url}'.format(host=self.host, url=url)
        referer = "http://{host}/game.php?village={id}&" \
                  "screen=report".format(host=self.host, id=self.global_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def post_confirmation(self, village_id, post_data):
        url = 'http://{host}/game.php?village={id}&' \
              'try=confirm&screen=place'.format(host=self.host, id=village_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=place'.format(host=self.host, id=village_id)
        content_length = len(post_data)
        headers = self._get_default_headers(referer=referer,
                                            content_length=content_length)
        data = {'url': url, 'headers': headers, 'data': post_data}
        return data

    def post_attack(self, village_id, csrf, post_data):
        url = 'http://{host}/game.php?village={id}&' \
              'action=command&h={csrf}&screen=place'.format(host=self.host,
                                                            id=village_id,
                                                            csrf=csrf)
        referer = 'http://{host}/game.php?village={id}&' \
                  'try=confirm&screen=place'.format(host=self.host,
                                                         id=village_id)
        content_length = len(post_data)
        headers = self._get_default_headers(referer=referer,
                                            content_length=content_length)
        data = {'url': url, 'headers': headers, 'data': post_data}
        return data

    def get_tribal_forum_page(self):
        url = "http://{host}/game.php?village={id}&" \
              "screen=forum".format(host=self.host, id=self.global_id)
        referer = "http://{host}/game.php?village={id}&" \
                  "screen=overview".format(host=self.host,
                                                id=self.global_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_forum_screen(self, forum_id):
        url = "http://{host}/game.php?village={v_id}&" \
              "screenmode=view_forum&forum_id={f_id}&" \
              "screen=forum".format(host=self.host,
                                    v_id=self.global_id,
                                    f_id=forum_id)
        referer = "http://{host}/game.php?village={v_id}&" \
                  "screen=forum".format(host=self.host, v_id=self.global_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_last_thread_page(self, forum_id, thread_id):
        url = "http://{host}/game.php?village={v_id}&" \
              "screenmode=view_thread&forum_id={f_id}&" \
              "thread_id={t_id}&page=last&screen=forum".format(host=self.host,
                                                               v_id=self.global_id,
                                                               f_id=forum_id,
                                                               t_id=thread_id)
        referer = "http://{host}/game.php?village={v_id}&" \
                  "screenmode=view_forum&forum_id={f_id}&" \
                  "screen=forum".format(host=self.host,
                                        v_id=self.global_id,
                                        f_id=thread_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_answer_page(self, forum_id, thread_id):
        url = "http://{host}/game.php?village={v_id}&" \
              "screenmode=view_thread&thread_id={t_id}&" \
              "answer=true&page=last&forum_id={f_id}&" \
              "screen=forum".format(host=self.host,
                                    v_id=self.global_id,
                                    f_id=forum_id,
                                    t_id=thread_id)
        referer = "http://{host}/game.php?village={v_id}&" \
                  "screenmode=view_thread&forum_id={f_id}&" \
                  "thread_id={t_id}&page=last&" \
                  "screen=forum".format(host=self.host,
                                        v_id=self.global_id,
                                        f_id=forum_id,
                                        t_id=thread_id)

        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def post_message_to_forum(self, forum_id, thread_id, post_data, csrf):
        # php URLs get longer and longer..
        url_begin = "http://{host}/game.php?village={v_id}&" \
                    "screenmode=view_thread&action=new_post&" \
                    "h={csrf}".format(host=self.host,
                                      v_id=self.global_id,
                                      csrf=csrf)
        url_end = "&thread_id={t_id}&answer=true&page=last&" \
                  "forum_id={f_id}&screen=forum".format(f_id=forum_id,
                                                        t_id=thread_id)
        url = url_begin + url_end
        referer = "http://{host}/game.php?village={v_id}&" \
                  "screenmode=view_thread&thread_id={t_id}&" \
                  "answer=true&page=last&forum_id={f_id}&" \
                  "screen=forum".format(host=self.host,
                                        v_id=self.global_id,
                                        f_id=forum_id,
                                        t_id=thread_id)
        content_length = len(post_data)
        headers = self._get_default_headers(referer=referer, content_length=content_length)

        data = {'url': url, 'headers': headers, 'data': post_data}
        return data

    def _get_default_headers(self, referer=None, content_length=None):
        """
        Returns headers that are common for each request
        """
        default_headers = {'host': '{host}'.format(host=self.host),
                           'connection': 'keep-alive',
                           'accept': 'text/html,application/xhtml+xml,'
                                      'application/xml;q=0.9,image/webp,*/*;q=0.8',
                           'user-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) '
                                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                                          'Chrome/30.0.1599.101 Safari/537.36',
                           'accept-encoding': 'gzip,deflate,sdch'}
        if referer is not None:
            default_headers['referer'] = referer
        if content_length is not None:
            default_headers['content-length'] = content_length

        return default_headers


class SafeOpener:

    def __init__(self, host, cookies, con_attempts, reconnect, username, password,
                 antigate_key):
        self.host = host
        self.cookies = cookies
        self.attempts = con_attempts
        self.reconnect = reconnect
        if reconnect:
            if not(username and password):
                raise AttributeError("Bot cannot re-connect automatically"
                                     "without username and password :(")
            else:
                self.auto_login = AutoLogin(host, username, password)
        if antigate_key:
            self.captcha_breaker = AntigateWrapper(antigate_key)
        else:
            self.captcha_breaker = None

    def send_request(self, request_data):
        return self._send_request(request_data, attempts=self.attempts)

    def _send_request(self, request_data, attempts):
        while attempts > 0:
            attempts -= 1
            try:
                url = request_data['url']
                headers = request_data['headers']
                post_data = request_data.get('data', None)
                if post_data:
                    resp = requests.post(url, headers=headers, data=post_data,
                                         cookies=self.cookies)
                else:
                    resp = requests.get(url, headers=headers,
                                        cookies=self.cookies)
                response_text = resp.text
                response_time = resp.headers['date']
                expiration_check = self._check_if_session_expire(response_text)
                if expiration_check:
                    if self.reconnect:
                        self._relogin_to_game_server()
                        # compensate attempts if re-login was successful
                        attempts += 1
                        continue
                    else:
                        raise SessionExpiredError
                captcha_url = self._check_if_captcha_spawned(response_text)
                if captcha_url:
                    self._handle_captcha(captcha_url, attempts)
                    attempts += 1
                    continue

                return {'response_text': response_text, 'response_time': response_time}

            except HTTPError:
                error_info = traceback.format_exception(*sys.exc_info())
                logging.error(error_info)
                continue
            # server is unreachable or actively refuses connection
            except URLError:
                error_info = traceback.format_exception(*sys.exc_info())
                logging.error(error_info)
                # do not hit server in a predictable manner
                time.sleep(30 + random.random() * 30)
                continue
            except ConnectionError:
                error_info = traceback.format_exception(*sys.exc_info())
                logging.error(error_info)
                time.sleep(30 + random.random() * 30)
                continue
            # strange & rare issue when unzipping some of TribalWars responses.
            # never reproduced 2 times in row (when repeating request)
            except struct.error:
                error_info = traceback.format_exception(*sys.exc_info())
                logging.error(error_info)

                continue
        raise TooManyConnectionAttempts("There were too many connection errors."
                                        "See log file for details.")

    def _check_if_session_expire(self, html_data):
        expiry_text = "Session expired"
        if expiry_text in html_data:
            logging.warning("Session expired... Don't worry, masta!")
            return True

    def _relogin_to_game_server(self):
        self.cookies = self.auto_login.login_to_server()

    def _check_if_captcha_spawned(self, html_data):
        protection_text = "Bot protection"
        if protection_text in html_data:
            logging.warning("Faced Captcha")
            # Extract captcha URL: it is inside JS function and
            # may look differently:
            # 1. '/human.php?s=afef3a5b97df&small'
            # 2. '/human.php?s=d775cf97c86e'
            img_url_ptrn = re.compile(r"""(/human.php[\W\w]+?)
                                          \W    # closing quote
                                          \){0,1}   # may have closing bracket
                                          ; # deterministic semicolon
                                       """, re.VERBOSE)
            # Extract CAPTCHA URL. Note: it's changing on each
            # subsequent request, do not refresh TW pages in browser
            # while waiting for captcha answer from Antigate
            url_match = re.search(img_url_ptrn, html_data)
            if url_match:
                captcha_url = 'http://{host}{match}'.format(host=self.host,
                                                            match=url_match.group(1))
                return captcha_url
            else:
                # Bot protection faced but we were not able to extract
                # URL for captcha image.
                raise AttributeError("Faced new type of TW captcha-page."
                                     "Check your TW account and fix this, bro!")

    def _handle_captcha(self, image_url, attempts):
        if not self.captcha_breaker:
            raise AttributeError("There are no captcha breakers available :(")
        img_bytes = self._download_img(image_url)
        text_anwser = self.captcha_breaker.get_captcha_answer(img_bytes)
        request_data = self._post_captcha_answer(text_anwser)
        self._send_request(request_data, attempts)

    def _download_img(self, image_url):
        logging.info("Handling CAPTCHA from the next "
                     "URL: {url}".format(url=image_url))
        response = urlopen(image_url)
        img_bytes = response.read()
        return img_bytes

    def _post_captcha_answer(self, text):
        url = "http://{host}/game.php".format(host=self.host)
        post_data = {'bot_check_code': text}
        headers = {}
        headers['user-agent'] = 'Mozilla/5.0 (Windows NT 6.1; WOW64) ' \
                                'AppleWebKit/537.36 (KHTML, like Gecko) ' \
                                'Chrome/30.0.1599.101 Safari/537.36'
        headers["origin"] = "http://{host}".format(host=self.host)
        headers["x-requested-with"] = "XMLHttpRequest"
        headers["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers['accept-encoding'] = 'gzip,deflate,sdch'

        data = {'url': url, 'headers': headers, 'data': post_data}
        return data
