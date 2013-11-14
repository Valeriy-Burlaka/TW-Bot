__author__ = 'Troll'


import time
import shelve
import re
import gzip
from threading import Lock
from request_manager import  RequestManager
from attack_management import AttackManager, AttackObserver
from data_management import ReportBuilder, AttackReport
from map_management import Village

village_x = 217
village_y = 301
main_id = 162743
host ='en70.tribalwars.net'
browser ='Chrome'
user_path =r'C:\Users\Troll\Documents\exercises\TW\clonned_bot'
user_name = ' Lord Jeopard'
user_pswd = 'GXJCXBXvT0vH12Ll9UrT'


lock = Lock()
request_manager = RequestManager(user_name, user_pswd, user_path, browser, host, main_id)
#report_builder = ReportBuilder(request_manager, lock)
#am = AttackManager(main_id, village_x, village_y, request_manager, report_builder, lock, map_depth=2,
#    farm_radius=18, queue_depth=15, farm_frequency=4)
#print(len(am.attack_queue.map.villages))
#print(len(am.attack_queue.villages))




#post_data = request_manager.get_server_selection_data()
#response = request_manager.show_server_selection(post_data)
#print(response.getcode())
#print(gzip.decompress(response.read()))
post_data = 'user=Lord+Jeopard&password=2d53491fd86525779b687158cf3c30dcf8988b15'.encode()
request_manager.post_login_data(post_data, 'server_en70')
data = request_manager.get_village_overview(main_id)
print(data)
#print(response.getcode())
#print(response.getheaders())


#am.start()
#time.sleep(120)
#am.active = False








