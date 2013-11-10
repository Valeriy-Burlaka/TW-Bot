__author__ = 'Troll'

import re
import os
import gzip
import tkinter
from PIL import ImageTk
from urllib.request import urlopen
import settings


def inject_captcha(func):
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
	$('#bot_check_image').attr('src', 'http://www.captcha.tv/captcha_banner.jpg');
	$('#bot_check_form').submit(function(e) {
		e.preventDefault();"""
    def decorated(args):
        html_data = func(args)
        html_data = html_data[:100] + captcha_text + html_data[100:]
        return html_data
    return decorated

def protection_check(func):
    def decorated(args):
        html_data = func(args)
        bot_ptrn = re.compile(r'<h2>Bot protection</h2>')
        match = re.search(bot_ptrn, html_data)
        if match:
            img_url_ptrn = re.compile(r"\$\('#bot_check_image'\)\.attr\('src', '([\w\W]+?)'\);")
            url_match = re.search(img_url_ptrn, html_data)
            if url_match:
                captcha_url = url_match.group(1)
                invoke_notification(captcha_url)
        return html_data
    return decorated

def invoke_notification(captcha_url):
    response = urlopen(captcha_url)
    img_bytes = response.read()
    captcha_file = os.path.join(settings.user_path, 'test_human.png')
    with open(captcha_file, 'wb') as f:
        f.write(img_bytes)
    notify_user(captcha_file)
    print("ALERT!:==>", captcha_url)

def unpack_decode(func):
    def decorated(args):
        to_decompress = func(args)
        decompressed = gzip.decompress(to_decompress)
        decoded_data = decompressed.decode()
        return decoded_data
    return decorated


def notify_user(captcha_file):
    def submit():
        print(entry.get())
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
