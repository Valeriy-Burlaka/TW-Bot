import os
import re
import random
import time
import shutil
import sqlite3
import gzip
import tkinter
from PIL import ImageTk
from urllib.request import Request
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import  HTTPError


class RequestManager:
    """
    Component responsible for sending requests to TribalWars server.
    Upon init, copies browser's (currently Chrome only) cookies (sqlite file)
    and extracts mandatory Game cookies from there ('sid', 'cid', 'mobile', 'global_vilage_id')
    Class should be further re-worked to accept 'global_village_id' dynamically to
    allow sending requests from 'different' villages.

    The trickiest part is that almost each response should be checked
    for "<h2>Bot protection</h2>": this means we faced CAPTCHA.
    If so, we're attempting to download CAPTCHA image and creating GUI blocking
    window (until we do not return control, caller Thread will not release Lock() &
    no additional calls will be made to RequestManager). When user submits what she
    sees, we're attempting to POST this value and unblocking the caller
    """


    def __init__(self, host='en70.tribalwars.net', browser='Chrome',
                 user_path=r'C:\Users\Troll\Documents\exercises\TW' ):
        self.browser = browser
        self.host = host
        self.user_path = user_path
        self.set_cookies()
        self.referer = None


    def get_map_overview(self, x, y):
        url = 'http://{host}/game.php?village=127591&{x}=211&{y}=305&screen=map'.format(host=self.host, x=x, y=y)
        self.referer = url
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_village_overview(self):
        url = 'http://{host}/game.php?village=127591&screen=overview'.format(host=self.host)
        self.referer = url
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_rally_overview(self):
        url = 'http://{host}/game.php?village=127591&screen=place'.format(host=self.host)
        self.referer = url
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_reports_page(self, from_page=0):
        url = 'http://{host}/game.php?village=127591&mode=all&from={page}&screen=report'.format(host=self.host,
                                                                                                page=from_page)
        self.referer = url
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def get_report(self, url):
        url = 'http://{host}{url}'.format(host=self.host, url=url)
        self.referer = "http://{host}/game.php?village=127591&screen=report".format(host=self.host)
        headers = self.get_default_headers()
        req = Request(url, headers=headers)
        return self.safe_opener(req)

    def post_confirmation(self, data):
        url = 'http://{host}/game.php?village=127591&try=confirm&screen=place'.format(host=self.host)
        self.referer = 'http://{host}/game.php?village=127591&screen=place'.format(host=self.host)
        headers = self.get_default_headers()
        headers['Content-Length'] = len(data)
        req = Request(url, headers=headers, data=data)
        return self.safe_opener(req)

    def post_attack(self, data, csrf):
        url = 'http://{host}/game.php?village=127591&action=command&h={csrf}&screen=place'.format(host=self.host, csrf=csrf)
        self.referer = 'http://{host}/game.php?village=127591&try=confirm&screen=place'.format(host=self.host)
        headers = self.get_default_headers()
        headers['Content-Length'] = len(data)
        headers['Origin'] = "http://{host}".format(host=self.host)
        req = Request(url, headers=headers, data=data)
        try:
            response = urlopen(req)
            # after POSTing an attack, Game automatically redirects to rally point
            self.get_rally_overview()
            return response.getheader('Date')
        except HTTPError as e:
            print(e)

    def safe_opener(self, request):
        """
        Wraps almost all calls to Game server into:
        1. Unzipping & decoding
        2. Protection check
        Returns unzipped&decoded response data
        """
        try:
            response = urlopen(request)
            data = response.read()
            return self.protection_check(self.unpack_decode(data))
        except HTTPError as e:
            print(e)

    def unpack_decode(self, data):
        decompressed = gzip.decompress(data)
        decoded_data = decompressed.decode()
        return decoded_data

    def protection_check(self, html_data):
        bot_ptrn = re.compile(r'<h2>Bot protection</h2>')
        match = re.search(bot_ptrn, html_data)
        if match:   # We have a problem
            img_url_ptrn = re.compile(r"\$\('#bot_check_image'\)\.attr\('src', '([\w\W]+?)'\);")
            # Extract CAPTCHA URL. Note: it's changing on each subsequent request, do not render response page in browser!
            url_match = re.search(img_url_ptrn, html_data)
            if url_match:
                captcha_url = 'http://{host}{match}'.format(host=self.host, match=url_match.group(1))
                try:
                    self.invoke_notification(captcha_url)
                except Exception as e:
                    print(e)
                    return
        return html_data

    def invoke_notification(self, captcha_url):
        """
        Downloads captcha from given URL and saves it to local file.
        Returns filename
        """
        response = urlopen(captcha_url)
        img_bytes = response.read()
        captcha_file = os.path.join(self.user_path, 'test_human.png')
        with open(captcha_file, 'wb') as f:
            f.write(img_bytes)

        self.notify_user(captcha_file)

    def notify_user(self, captcha_file):
        """
        Initializes GUI window with label=captcha image.
        Does not return until user submits what she sees on the picture.
        """
        def submit():
            submit = self.submit_captcha(entry.get())
            if submit:
                root.quit()

        root = tkinter.Tk()
        img = ImageTk.PhotoImage(file=captcha_file)
        label = tkinter.Label(root, image=img)
        label.pack()
        entry = tkinter.Entry(root)
        entry.pack()
        btn = tkinter.Button(text='Submit captcha', command=submit)
        btn.pack()
        root.mainloop()

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
        print(req.headers, req.data, req.full_url)
        response = urlopen(req)
        if response.getcode() == '200' or response.getcode() == 200:
            return True

    def get_default_headers(self):
        """
        Returns headers that are common for each request
        """
        default_headers = [('Host','{host}'.format(host=self.host)),
                           ('Connection', 'keep-alive'),
                           ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
                           ('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36'),
                           ('Accept-Encoding', 'gzip,deflate,sdch'),
                           ('Accept-Language', 'en-US,en;q=0.8'),
                           ('Referer', self.referer),
                           ('Cookie', self.cookies)]
        return dict(default_headers)

    def set_cookies(self):
        """
        Sets self.cookies attribute to composed cookies string.
        E.g.: self.cookies = 'cid=2125181249; sid=0%3A24ee69a57ec6; ...'
        """
        cookies_file = self.copy_cookies_file()
        cookies_data = self.extract_cookies(cookies_file)   # [(host, cookie, value), ..]
        mandatory_cookies = self.get_mandatory_cookies()
        # sort out host from cookies_data.
        cookies_data = [(item[1], item[2]) for item in cookies_data if item[1] in mandatory_cookies]
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
        return ['cid', 'sid', 'mobile', 'global_village_id']

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
        my_cookies_f = os.path.join(self.user_path, "cookies")
        shutil.copyfile(chr_cookies, my_cookies_f)
        return my_cookies_f


    def inject_captcha(self, html_data):
        """
        Test function which can be used with self.safe_opener to verify
        workability of notification process.
        Note: after submission, Game URLs of kind '/human.php?s=24ee69a57ec6&small'
        contain no image, so PIL.ImageTk will raise 'NoImage' exception.
        To test, either replace URL in captcha_text to still valid CAPTCHA URL,
        or with any image URL (& adjust self.submit_captcha to not insert self.host in URL)
        """
        captcha_text = """
                        <h2>Bot protection</h2>
                        <div id="bot_check_error" style="color:red; font-size:large; display: none"></div>
                        <img id="bot_check_image" src="/graphic/map/empty.png"" alt="" /><br /><br />
                        <form id="bot_check_form" method="post" action="">
                        Enter the numbers and letters into the text field: <input id="bot_check_code" type="text" name="code" style="width: 70px"/> <input id="bot_check_submit" class="btn" type="submit" value="Continue"/>
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

    def get_reports_page(self):
        report_pages = ['report_page.html']
        report_page_file = random.choice(report_pages)
        report_page_path = os.path.join('test_html', report_page_file)
        with open(report_page_path) as f:
            html_data = f.read()
        return html_data

    def get_report(self, url):
        reports = ['single_report_green.html', 'single_report_yellow.html']

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


