import time
import sys
from threading import Lock
from request_manager import  RequestManager
from village_management import VillageManager
from attack_management import AttackManager
from data_management import ReportBuilder
from map_management import Map

lock = Lock()
base_x = 211
base_y = 305
main_id = 127591
host = 'en70.tribalwars.net'
browser = 'Chrome'
user_path = r'C:\Users\Troll\Documents\exercises\TW\clonned_bot'
user_name = 'Chebutroll'
user_pswd = 'cjiy47H5MamVephlVddV'
farm_with = (127591, 126583)
t_limit = 4
observer_file = 'test_observer_data'

request_manager = RequestManager(user_name, user_pswd, user_path, browser, host, main_id)
village_manager = VillageManager(request_manager, lock, main_id, farm_with, t_limit_to_leave=t_limit)
report_builder = ReportBuilder(request_manager, lock)
map = Map(base_x, base_y, request_manager, lock, depth=2, mapfile='map')

attack_manager = AttackManager(request_manager, lock, village_manager, report_builder, map, observer_file)

try:
    attack_manager.start()
    time.sleep(18000)
    attack_manager.active = False

except KeyboardInterrupt:
    attack_manager.active = False
    sys.exit()