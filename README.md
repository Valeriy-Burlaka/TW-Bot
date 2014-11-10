### This thingy was created solely in educaional purposes and should not be used, intentionally or not.

#### About thingy:
* Farming bot for TW browser game
* Buildings & their levels are parsed with BSoup (set language-specific names in 'bot.app.locale.py')
* Server-specific settings (server speed, etc.): 'settings.py'.
* Thingy doesn't use clicks, but only requests to game API. 
* Thingy uses dirty mechanic & fragile mechanic of getting session-key (from local browser cookies). Thus, user is not superseded from his current session and can observe how thingy performs.
* Thingy was tested last time in March 2014, with those days Chromium-like browsers & Windows/Debian OSs. 
* Thingy handles CAPTCHA through [Antigate service] (http://antigate.com). Valid key is need to be set in 'settings.py'.

#### Thingy requires:
1. Python3.
2. "pip install -r requirements.txt".
3. carefully edited "settings.py" file.
4. successful "python runner.py" command.

