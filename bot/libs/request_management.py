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


__all__ = ['RequestManager', 'SessionExpiredError', 'TooManyConnectionAttempts',
           'RequestDataProvider', 'SafeOpener']


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
    """
    A manager class that breaks request sending into 2 parts:
    1. Delegates all method calls to RequestDataProvider class to get
    request data to send.
    2. Delegates sending of request to SafeOpener class which performs
    error handling & primary verification of response data (expiration
    of user session & bot protection)
    """

    def __init__(self, host, initial_cookies, main_id, locale, con_attempts,
                 reconnect=False, username=None, password=None, antigate_key=None):
        self.safe_opener = SafeOpener(host, initial_cookies, locale, con_attempts,
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
    """
    Summarizes all available methods that interact with game server.
    Each method 'mirrors' in-game requests made by user.
    """

    def __init__(self, host, global_id):
        self.host = host
        self.global_id = global_id

    def get_map_overview(self, x, y, village_id):
        """
        User opens game map. X and Y coordinates are used un URL to
        mimic map opening from non-user village.
        """
        url = 'http://{host}/game.php?village={id}&x={x}&y={y}&' \
              'screen=map'.format(host=self.host,
                                  id=village_id,
                                  x=x,
                                  y=y)
        headers = self._get_default_headers(referer=url)
        data = {'url': url, 'headers': headers}
        return data

    def get_overviews_screen(self):
        """
        Screen that contains listing of all user villages
        """
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
        """
        Main screen of player's village.
        """
        url = 'http://{host}/game.php?village={id}&' \
              'screen=overview'.format(host=self.host, id=village_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=overview_villages'.format(host=self.host,
                                                    id=village_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_train_screen(self, village_id):
        """
        Game screen that contains full listing of units that belong
        to this village.
        """
        url = 'http://{host}/game.php?village={id}&' \
              'screen=train'.format(host=self.host, id=village_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=overview'.format(host=self.host, id=village_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_rally_overview(self, village_id):
        """
        Game screen that allows to send attacks and contains a listing of all
        attacks that were sent.
        """
        url = 'http://{host}/game.php?village={id}&' \
              'screen=place'.format(host=self.host, id=village_id)
        referer = 'http://{host}/game.php?village={id}&' \
                  'screen=overview'.format(host=self.host, id=village_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_reports_page(self, from_page):
        """
        Game page with list of reports.
        """
        url = 'http://{host}/game.php?village={id}&mode=all&' \
              'from={page}&screen=report'.format(host=self.host,
                                                 id=self.global_id,
                                                 page=from_page)
        headers = self._get_default_headers(referer=url)
        data = {'url': url, 'headers': headers}
        return data

    def get_report(self, url):
        """
        Game page of one particular report.
        """
        url = 'http://{host}{url}'.format(host=self.host, url=url)
        referer = "http://{host}/game.php?village={id}&" \
                  "screen=report".format(host=self.host, id=self.global_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def post_confirmation(self, village_id, post_data):
        """
        POST request that is sent when user hits 'Attack' button in rally point.
        Redirects user to 'Attack' screen.
        """
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
        """
        POST request that is sent when user hits 'OK' button in 'Attack' screen.
        (sends an attack).
        """
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

    # The methods below are not related to sending attacks, but automate
    # the procedure of posting forum messages.

    def get_tribal_forum_page(self):
        """
        Main page of tribal forum.
        """
        url = "http://{host}/game.php?village={id}&" \
              "screen=forum".format(host=self.host, id=self.global_id)
        referer = "http://{host}/game.php?village={id}&" \
                  "screen=overview".format(host=self.host,
                                                id=self.global_id)
        headers = self._get_default_headers(referer=referer)
        data = {'url': url, 'headers': headers}
        return data

    def get_forum_screen(self, forum_id):
        """
        Particular forum
        """
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
        """
        Particular thread on forum.
        """
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
        """
        Page with message form.
        """
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
        """
        POST request that posts message on forum.
        """
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
    """
    Tries to send request with a pre-defined number of attempts.
    Takes 'live' cookies (working session_id, etc.) to 'spoof' the
    real user on the wire.
    Checks response text for the next things:

        1. Whether user session was expired.
        2. Whether we faced bot protection (captcha).

    and handles the situations above according to initial settings:

        1. If asked to re-connect automatically and username & password
        were provided, re-connects to game server using AutoLogin class
        and uses new cookies (cid, sid) to perform all next requests.
        2. If Antigate API key is provided, uses AntigateWrapper class
        to 'break' the captcha.
    """

    def __init__(self, host, cookies, locale, con_attempts, reconnect,
                 username, password, antigate_key):
        self.host = host
        self.cookies = cookies
        self.locale = locale
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
                # sometimes game server returns empty response
                if len(response_text) == 0:
                    continue
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
        """
        Checks for a language-specific text that indicates that user session
        has been expired.
        """
        expiry_text = self.locale["expiration"]
        if expiry_text in html_data:
            logging.warning("Session expired... Don't worry, masta!")
            return True

    def _relogin_to_game_server(self):
        self.cookies = self.auto_login.login_to_server()

    def _check_if_captcha_spawned(self, html_data):
        """
        Checks for a language-specific text in the response page that
        indicates that we have faced with bot protection (CAPTCHA).
        If so, tries to extract (unique) URL for CAPTCHA image.
        """
        protection_text = self.locale["protection"]
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
        """
        Tries to download CAPTCHA image and to 'decipher' it with Antigate
        service, then POSTs the answer to game server.
        """
        if not self.captcha_breaker:
            raise AttributeError("There are no captcha breakers available :(")
        img_bytes = self._download_img(image_url)
        text_anwser = self.captcha_breaker.get_captcha_answer(img_bytes)
        request_data = self._post_captcha_answer(text_anwser)
        self._send_request(request_data, attempts)

    @staticmethod
    def _download_img(image_url):
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
