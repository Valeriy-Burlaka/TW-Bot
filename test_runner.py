import time
import sys
import os
from threading import Lock
from request_manager import  RequestManager, DummyRequestManager
from village_management import VillageManager
from attack_management import AttackManager
from data_management import ReportBuilder
from map_management import Map, Village

run_name = time.strftime("%d %b %H-%M-%S GMT", time.gmtime())
run_path = os.path.join(sys.path[0], "bot_runs", run_name)
if not os.path.exists(run_path):
    os.makedirs(run_path)
logfile = os.path.join(run_path, "errors_log.txt")
events_file = os.path.join(run_path, "activity_log.txt")

browser = 'Chrome'
host = 'en70.tribalwars.net'
user_name = 'Chebutroll'
user_pswd = 'cjiy47H5MamVephlVddV'
base_x = 211
base_y = 305
main_id = 127591
farm_with = (127591, 126583,)
t_limit = 4
observer_file = 'test_observer_data'

lock = Lock()
request_manager = RequestManager(user_name, user_pswd, browser, host, main_id, run_path, logfile, events_file)
village_manager = VillageManager(request_manager, lock, main_id, farm_with, events_file,
                                use_def_to_farm=False, heavy_is_def=True, t_limit_to_leave=t_limit)
report_builder = ReportBuilder(request_manager, lock, run_path)

map = Map(base_x, base_y, request_manager, lock, run_path, events_file, depth=2, mapfile='new_map')

attack_manager = AttackManager(request_manager, lock, village_manager, report_builder, map, observer_file, logfile, events_file)

try:
    attack_manager.start()
    time.sleep(3600 * 5)
    attack_manager.active = False

except KeyboardInterrupt:
    attack_manager.active = False
    sys.exit()