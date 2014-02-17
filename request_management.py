import os
import sys
import re
import random
import time
import base64
import shutil
import sqlite3
import gzip
import struct
import logging
import traceback
from urllib.request import Request, urlopen
from urllib.request import build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
from urllib.error import  HTTPError, URLError
from http.cookiejar import CookieJar


class RequestManager:
    """
    Component responsible for sending requests to TribalWars server.
    Upon init, copies browser's (currently Chrome only) cookies (sqlite file)
    and extracts mandatory Game cookies from there ('sid' & 'cid' tokens).

    Checks each response data for the next things:
    1. "<h2>Bot protection</h2>" element: this means we faced CAPTCHA.
    If so, we attempt to download CAPTCHA image and create GUI blocking
    window (until we do not return control, caller Thread will not release Lock() and
    no additional calls will be made to RequestManager). When user submits what she
    sees, we attempt to POST this value and unblock the caller.

    2. "<h2>Session expired</h2>" element:
    this means that session has expired. We try to
    re-connect to server, update self.ccokies and re-submit
    the last Request with new cookies.
    """

    def __init__(self, user_name, user_pswd, browser, host, main_id,
                 run_path, antigate_key):
        self.user_name = user_name
        self.user_pswd = user_pswd
        self.browser = browser
        self.antigate_key = antigate_key
        self.host = host
        self.main_id = str(main_id)
        self.run_path = run_path
        self.set_cookies()
        self.referer = None

    def get_map_overview(self, village_id, x, y):
        url = 'http://{host}/game.php?village={id}&x={x}&y={y}&' \
              'screen=map'.format(host=self.host,
                                  id=village_id, x=x, y=y)
        self.referer = url
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_overviews_screen(self):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=overview_villages&mode=combined'.format(host=self.host,
                                                              id=self.main_id)
        self.referer = 'http://{host}/game.php?village={id}&' \
                       'screen=overview'.format(host=self.host,
                                                id=self.main_id)
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_village_overview(self, village_id):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=overview'.format(host=self.host, id=village_id)
        self.referer = 'http://{host}/game.php?village={id}&' \
                       'screen=overview_villages'.format(host=self.host,
                                                         id=self.main_id)
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_train_screen(self, village_id):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=train'.format(host=self.host, id=village_id)
        self.referer = 'http://{host}/game.php?village={id}&' \
                       'screen=overview'.format(host=self.host, id=village_id)
        headers = self.get_default_headers()
        self.replace_global_id(headers, village_id)
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_rally_overview(self, village_id):
        url = 'http://{host}/game.php?village={id}&' \
              'screen=place'.format(host=self.host, id=village_id)
        self.referer = 'http://{host}/game.php?village={id}&' \
                       'screen=overview'.format(host=self.host, id=village_id)
        headers = self.get_default_headers()
        self.replace_global_id(headers, village_id)
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_reports_page(self, from_page=0):
        url = 'http://{host}/game.php?village={id}&mode=all&' \
              'from={page}&screen=report'.format(host=self.host,
                                                 id=self.main_id,
                                                 page=from_page)
        self.referer = url
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_report(self, url):
        url = 'http://{host}{url}'.format(host=self.host, url=url)
        self.referer = "http://{host}/game.php?village={id}&" \
                       "screen=report".format(host=self.host, id=self.main_id)
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def post_confirmation(self, village_id, data):
        url = 'http://{host}/game.php?village={id}&' \
              'try=confirm&screen=place'.format(host=self.host, id=village_id)
        self.referer = 'http://{host}/game.php?village={id}&' \
                       'screen=place'.format(host=self.host, id=village_id)
        headers = self.get_default_headers()
        self.replace_global_id(headers, village_id)
        headers['Content-Length'] = len(data)
        req = Request(url, headers=headers, data=data)
        return self.safe_opener(req)

    def post_attack(self, village_id, data, csrf):
        url = 'http://{host}/game.php?village={id}&' \
              'action=command&h={csrf}&screen=place'.format(host=self.host,
                                                            id=village_id,
                                                            csrf=csrf)
        self.referer = 'http://{host}/game.php?village={id}&' \
                       'try=confirm&screen=place'.format(host=self.host,
                                                         id=village_id)
        headers = self.get_default_headers()
        self.replace_global_id(headers, village_id)
        headers['Content-Length'] = len(data)
        req = Request(url, headers=headers, data=data)
        response = urlopen(req)
        # after POSTing an attack, Game automatically redirects to rally point
        self.get_rally_overview(village_id)
        return response.getheader('Date')

    def get_tribal_forum_page(self):
        url = "http://{host}/game.php?village={id}&" \
              "screen=forum".format(host=self.host, id=self.main_id)
        self.referer = "http://{host}/game.php?village={id}&" \
                       "screen=overview".format(host=self.host,
                                                id=self.main_id)
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_forum_screen(self, forum_id):
        url = "http://{host}/game.php?village={v_id}&" \
              "screenmode=view_forum&forum_id={f_id}&" \
              "screen=forum".format(host=self.host,
                                    v_id=self.main_id,
                                    f_id=forum_id)
        self.referer = "http://{host}/game.php?village={v_id}&" \
                       "screen=forum".format(host=self.host, v_id=self.main_id)
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_last_thread_page(self, forum_id, thread_id):
        url = "http://{host}/game.php?village={v_id}&" \
              "screenmode=view_thread&forum_id={f_id}&" \
              "thread_id={t_id}&page=last&screen=forum".format(host=self.host,
                                                               v_id=self.main_id,
                                                               f_id=forum_id,
                                                               t_id=thread_id)
        self.referer = "http://{host}/game.php?village={v_id}&" \
                       "screenmode=view_forum&forum_id={f_id}&" \
                       "screen=forum".format(host=self.host,
                                             v_id=self.main_id,
                                             f_id=forum_id)
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_answer_page(self, forum_id, thread_id):
        url = "http://{host}/game.php?village={v_id}&" \
              "screenmode=view_thread&thread_id={t_id}&" \
              "answer=true&page=last&forum_id={f_id}&" \
              "screen=forum".format(host=self.host,
                                    v_id=self.main_id,
                                    f_id=forum_id,
                                    t_id=thread_id)
        self.referer = "http://{host}/game.php?village={v_id}&" \
                       "screenmode=view_thread&forum_id={f_id}&" \
                       "thread_id={t_id}&page=last&" \
                       "screen=forum".format(host=self.host,
                                             v_id=self.main_id,
                                             f_id=forum_id,
                                             t_id=thread_id)

        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def post_message_to_forum(self, forum_id, thread_id, csrf, message_data):
        # php URLs get longer and longer..
        url_begin = "http://{host}/game.php?village={v_id}&" \
                    "screenmode=view_thread&action=new_post&" \
                    "h={csrf}".format(host=self.host,
                                      v_id=self.main_id,
                                      csrf=csrf)
        url_end = "&thread_id={t_id}&answer=true&page=last&" \
                  "forum_id={f_id}&screen=forum".format(t_id=thread_id,
                                                        f_id=forum_id)
        url = url_begin + url_end
        self.referer = "http://{host}/game.php?village={v_id}&" \
                       "screenmode=view_thread&thread_id={t_id}&" \
                       "answer=true&page=last&forum_id={f_id}&" \
                       "screen=forum".format(host=self.host,
                                             v_id=self.main_id,
                                             f_id=forum_id,
                                             t_id=thread_id)

        headers = self.get_default_headers()
        headers['Content-Length'] = len(message_data)
        req = Request(url, headers=headers, data=message_data)
        response = urlopen(req)
        return response.getheader('Date')

    def safe_opener(self, request):
        """
        Wraps almost all calls to Game server into:
        1. Unzipping & decoding
        2. Session expiration check (invokes login
        procedure if session has expired)
        3. Protection check
        Returns unzipped & decoded response data.
        """
        try:
            response = urlopen(request)
            data = response.read()
            if self.expiration_check(self.unpack_decode(data)):
                self.login_to_server()
                request.add_header('Cookie', self.cookies)
                response = urlopen(request)
                data = response.read()
                response_data = self.protection_check(self.unpack_decode(data))
            else:
                response_data = self.protection_check(self.unpack_decode(data))
            return response_data
        except HTTPError:
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
        # server is unreachable or actively refuses connection
        except URLError:
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
            # do not hit server in a predictable manner
            time.sleep(30 + random.random() * 30)
            # re-submit the latest Request
            return self.safe_opener(request)
        except ConnectionError: # ConnectionResetError
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
            time.sleep(30 + random.random() * 30)
            return self.safe_opener(request)
        # strange & rare issue when unzipping some of TribalWars responses.
        # never reproduced 2 times in row (when repeating request)
        except struct.error:
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
            return self.safe_opener(request)

    def unpack_decode(self, data):
        decompressed = gzip.decompress(data)
        decoded_data = decompressed.decode()
        return decoded_data

    def protection_check(self, html_data):
        bot_ptrn = re.compile(r'<h2>Bot protection</h2>')
        match = re.search(bot_ptrn, html_data)
        if match:   # We have a problem
            logging.warning("Faced Captcha")
            img_url_ptrn = re.compile(r"\$\('#bot_check_image'\)\.attr\('src', '([\w\W]+?)'\);")
            # Extract CAPTCHA URL. Note: it's changing on each
            # subsequent request, do not render response page in browser!
            url_match = re.search(img_url_ptrn, html_data)
            if url_match:
                captcha_url = 'http://{host}{match}'.format(host=self.host,
                                                            match=url_match.group(1))
                self.handle_captcha(captcha_url)

        return html_data

    def handle_captcha(self, captcha_url):
        logging.warning("Handling CAPTCHA from the next "
                        "URL: {url}".format(url=captcha_url))

        response = urlopen(captcha_url)
        img_bytes = response.read()
        captcha_text = self.get_captcha_text(img_bytes)
        self.submit_captcha(captcha_text)
        logging.warning("Submitted CAPTCHA through Antigate, "
                        "text: {text}".format(text=captcha_text))
        captcha_file = os.path.join(self.run_path,
                                    '{text}_test_human.png'.format(text=captcha_text))
        with open(captcha_file, 'wb') as f:
            f.write(img_bytes)

    def get_captcha_text(self, img_bytes):
        b64_img = base64.b64encode(img_bytes)
        req_data = {'method': 'base64',
                    'key': self.antigate_key,
                    'body': b64_img,
                    'numeric': '1', 'min_len': '6', 'max_len': '6'}
        req_data = urlencode(req_data).encode()
        req = Request('http://antigate.com/in.php', data=req_data)
        response = urlopen(req)
        resp_data = response.read().decode()    # response.read() = b'OK|captcha_ID'
        if resp_data == 'ERROR_NO_SLOT_AVAILABLE':
            time.sleep(10)
            return self.get_captcha_text(img_bytes)
        elif resp_data.startswith("ERROR"):
            raise AttributeError(resp_data)

        captcha_id = resp_data.split('|')[1]
        captcha_url = 'http://antigate.com/res.php?key={api_key}&' \
                      'action=get&id={cap_id}'.format(api_key=self.antigate_key,
                                                      cap_id=captcha_id)
        captcha_text = ""
        time.sleep(10)  # average time of handling CAPTCHA on AntiGate service
        while not captcha_text:
            get_text_req = Request(captcha_url)
            response = urlopen(get_text_req)
            captcha_status = response.read().decode()
            # It's not a typo (CAPCHA)
            if captcha_status == 'CAPCHA_NOT_READY':
                time.sleep(5)
                continue
            elif captcha_status.startswith('OK'):
                captcha_text = captcha_status.split('|')[1]
            elif captcha_status.startswith("ERROR"):
                raise AttributeError(captcha_status)

        return captcha_text

    def submit_captcha(self, text):
        """
        Tries to restore Game's loyalty to user:
        submits CAPTCHA text entered by User to Game server
        """
        data = urlencode({'bot_check_code': text})
        data = data.encode()
        headers = self.get_default_headers()
        headers["Content-Length"] = len(data)
        headers["Origin"] = "http://{host}".format(host=self.host)
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        url = "http://{host}/game.php".format(host=self.host)

        req = Request(url, data=data, headers=headers)
        event_msg = str(req.headers) + str(req.data) + str(req.full_url)
        logging.debug(event_msg)
        urlopen(req)

    def expiration_check(self, html_data):
        """
        Checks if session has expired (specific header will be in
        HTML response. If so, invokes login procedure.
        """
        match = re.search('Session expired', html_data)
        if match:
            logging.warning("Session expired...Don't worry, masta!")
            return True

    def login_to_server(self):
        post_data = self.get_server_selection_data()
        response = self.show_server_selection(post_data)
        b_selection_data = gzip.decompress(response.read())
        selection_data = b_selection_data.decode()
        encrypt_pass = self.get_login_data(selection_data)
        post_data = urlencode([('user', self.user_name),
                               ('password', encrypt_pass)])
        post_data = post_data.encode()
        server = 'server_' + self.host.split('.')[0]
        self.post_login_data(post_data, server)
        self.get_village_overview(self.main_id)

    def get_server_selection_data(self):
        """
        Prepares POST data to submit
        "/index.php?action=login&show_server_selection=1" request.
        """
        user = ('user', self.user_name)
        pswd = ('password', self.user_pswd)
        cookie = ('cookie', 'false')
        check = ('clear', 'true')
        post_data = urlencode([user, pswd, cookie, check])
        return post_data.encode()

    def show_server_selection(self, post_data):
        """
        POSTs server selection request. Response contains encrypted
        user password for further POST.
        """
        host = 'www.tribalwars.net'
        url = 'http://' + host + '/index.php?action=login&' \
                                 'show_server_selection=1'
        headers = self.get_default_headers()
        headers['Host'] = host
        headers['Content-Length'] = len(post_data)
        headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
        headers['Origin'] = 'http://{}'.format(host)
        headers['X-Requested-With'] = 'XMLHttpRequest'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Referer'] = 'http://www.tribalwars.net'
        req = Request(url, headers=headers, data=post_data)
        response = urlopen(req)
        return response

    def get_login_data(self, selection_data):
        """
        Parses response received after 'show_server_selection' request.
        Returns encrypted user password.
        """
        pswd_ptrn = re.compile(r'password[\W\w]+?value\W\W"([\W\w]+?)\W"')
        match = re.search(pswd_ptrn, selection_data)
        return match.group(1)


    def post_login_data(self, post_data, server):
        cj = CookieJar()
        opener = build_opener(HTTPCookieProcessor(cj))

        host = 'www.tribalwars.net'
        url = 'http://' + host + '/index.php?action=login&' \
                                 '{server}'.format(server=server)
        headers = self.get_default_headers()
        headers.pop('Cookie')
        headers['Host'] = host
        headers['Content-Length'] = len(post_data)
        headers['Origin'] = 'http://' + host
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Referer'] = 'http://' + host
        req = Request(url, headers=headers, data=post_data)
        opener.open(req)
        cookies_data = []
        for cook in cj:
            cookies_data.append((cook.name, cook.value))
        cookies_data.append(('global_village_id', self.main_id))
        self.cookies = self.form_cookie_header(cookies_data)

    def get_default_headers(self):
        """
        Returns headers that are common for each request
        """
        default_headers = [('Host','{host}'.format(host=self.host)),
                           ('Connection', 'keep-alive'),
                           ('Accept', 'text/html,application/xhtml+xml,'
                                      'application/xml;q=0.9,image/webp,*/*;q=0.8'),
                           ('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) '
                                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                                          'Chrome/30.0.1599.101 Safari/537.36'),
                           ('Accept-Encoding', 'gzip,deflate,sdch'),
                           ('Accept-Language', 'en-US,en;q=0.8'),
                           ('Referer', self.referer),
                           ('Cookie', self.cookies)]
        return dict(default_headers)

    def replace_global_id(self, headers, villa_id):
        cook = headers['Cookie']
        cook = re.sub(r'global_village_id=\d{6}',
                      'global_village_id={id}'.format(id=villa_id), cook)
        headers['Cookie'] = cook

    def set_cookies(self):
        """
        Sets self.cookies attribute to composed cookies string.
        E.g.: self.cookies = 'cid=2125181249; sid=0%3A24ee69a57ec6; ...'
        """
        cookies_file = self.copy_cookies_file()
        cookies_data = self.extract_cookies(cookies_file)   # [(host, cookie, value), ..]
        mandatory_cookies = self.get_mandatory_cookies()
        # sort out host from cookies_data.
        cookies_data = [(item[1], item[2]) for
                        item in cookies_data if
                        item[1] in mandatory_cookies]
        cookies_data.extend([('mobile', '0'),
                             ('global_village_id',
                              self.main_id)])
        self.cookies = self.form_cookie_header(cookies_data)

    def form_cookie_header(self, cookies_data):
        """
        Composes given cookies data into 1 string.
        Returns a tuple ('Cookie', cookie_string) which is ready to use as request header.
        """
        str_value = ''
        for cookie in cookies_data:
            str_cookie = cookie[0]+ '=' + cookie[1]
            str_value += str_cookie
            str_value += '; '
        str_value = str_value.rstrip('; ')
        return str_value

    def get_mandatory_cookies(self):
        return ['cid', 'sid']

    def extract_cookies(self, cookies_path, timeout=30):
        """
        Open given sqlite file and extracts cookies that belong to self.host.
        Returns list of tuples [(host, cookie, value), ...]
        """
        #key = re.search(r'http://([\w\W]+)', self.host).group()
        connection = sqlite3.connect(cookies_path, timeout=timeout)
        cursor = connection.cursor()
        cursor.execute("select host_key, name, value from cookies where host_key=?", (self.host,))
        cookies_data = cursor.fetchall()
        cursor.close()
        connection.close()
        return cookies_data

    def copy_cookies_file(self):
        """
        Copies cookies file to user_path (Currently supports only Chrome:)).
        Returns filename of cookies copy.
        """
        if self.browser == 'Chrome':
            chr_cookies = r'C:\Users\Troll\AppData\Local\Google\Chrome\User Data\Default\Cookies'
        my_cookies_f = os.path.join(self.run_path, "cookies")
        shutil.copyfile(chr_cookies, my_cookies_f)
        return my_cookies_f


    def inject_captcha(self, html_data):
        """
        Test function which can be used with self.safe_opener to verify
        workability of notification process.
        Note: after submission, Game URLs of kind '/human.php?s=24ee69a57ec6&small'
        contain no image.
        To test, either replace URL in captcha_text to still valid CAPTCHA URL,
        or with any image URL (& adjust self.submit_captcha to not insert self.host in URL)
        """
        captcha_text = """
                        <h2>Bot protection</h2>
                        <div id="bot_check_error" style="color:red; font-size:large;
                        display: none"></div>
                        <img id="bot_check_image" src="/graphic/map/empty.png""
                        alt="" /><br /><br />
                        <form id="bot_check_form" method="post" action="">
                        Enter the numbers and letters into the text field:
                        <input id="bot_check_code" type="text" name="code" style="width: 70px"/>
                        <input id="bot_check_submit" class="btn" type="submit" value="Continue"/>
                        </form>
                        </div>
                        <script type="text/javascript">
                        //<![CDATA[
                        $(function() {
                        $('#bot_check_image').attr('src', '/human.php?s=24ee69a57ec6&small');
                        $('#bot_check_form').submit(function(e) {
                            e.preventDefault();"""
        html_data = html_data[:100] + captcha_text + html_data[100:]
        return html_data


class DummyRequestManager:
    """
    A stub for ReportBuilder & Map classes.
    Provides methods that returns str_HTML from hardcoded
    files instead of real server-response.
    """
    def get_map_overview(self, x, y):
        files = ['map_overview_200_300.html', 'map_overview_200_327.html',
                 'map_overview_211_305.html', 'map_overview_224_324.html',
                 'map_overview_228_300.html']
        map_file = random.choice(files)
        map_path = os.path.join('test_html', map_file)
        with open(map_path) as f:
            html_data = f.read()
        return html_data

    def get_village_overview(self):
        file = 'test_html/village_overview.html'
        with open(file) as f:
            html_data = f.read()
        return html_data

    def get_rally_overview(self):
        file = 'test_html/rally_point_overview.html'
        with open(file) as f:
            html_data = f.read()
        return html_data

    def get_reports_page(self, from_page=0):
        report_pages = ['report_page.html', 'report_page_with_new_supports.html',
                        'report_page2.html']
        report_page_file = random.choice(report_pages)
        report_page_path = os.path.join('test_html', report_page_file)
        with open(report_page_path) as f:
            html_data = f.read()
        return html_data

    def get_report(self, url):
        reports = ['single_report_yellow.html',
                   'red_blue_html_report.html',
                   'single_report_blue.html',
                   'yellow_report_w_defence.html',
                   'single_report_support.html',
                   'float_report.html',
                   'single_report_green.html',
                   'green_report_wo_scouts.html',
                   'single_report_red.html']

        report_file = random.choice(reports)
        report_path = os.path.join('test_html', report_file)
        with open(report_path) as f:
            html_data = f.read()
        return html_data

    def post_confirmation(self, data):
        file = 'test_html/attack_confirmation.html'
        with open(file) as f:
            html_data = f.read()
        return html_data

    def post_attack(self, data):
        self.get_rally_overview()
        return time.mktime(time.gmtime())


