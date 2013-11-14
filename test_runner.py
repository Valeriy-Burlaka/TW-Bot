import time
import sys
from threading import Lock
from request_manager import  RequestManager
from attack_management import AttackManager
from data_management import ReportBuilder

village_x = 211
village_y = 305
main_id = 127591
host ='en70.tribalwars.net'
browser ='Chrome'
user_path =r'C:\Users\Troll\Documents\exercises\TW\clonned_bot'
user_name = 'Chebutroll'
user_pswd = 'cjiy47H5MamVephlVddV'
lock = Lock()

request_manager = RequestManager(user_name, user_pswd, user_path, browser, host, main_id)
report_builder = ReportBuilder(request_manager, lock)
am = AttackManager(main_id, village_x, village_y, request_manager, report_builder, lock, map_depth=2,
    farm_radius=18, queue_depth=15, farm_frequency=4)

try:     
    am.start()
    time.sleep(18000)
    am.active = False
except KeyboardInterrupt:
    am.active = False
    sys.exit()