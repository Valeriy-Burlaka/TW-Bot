__author__ = 'Troll'


#import time
#import shelve
#import re
#import gzip
from threading import Lock
from request_manager import RequestManager
#from attack_management import AttackManager, AttackObserver
#from data_management import ReportBuilder, AttackReport
#from map_management import Village
from village_management import PlayerVillage, VillageManager


village_x = 211
village_y = 305
main_id = 127591
farm_with = [127591, 135035, 126583]
host ='en70.tribalwars.net'
browser ='Chrome'
user_path =r'C:\Users\Troll\Documents\exercises\TW\clonned_bot'
user_name = 'Chebutroll'
user_pswd = 'cjiy47H5MamVephlVddV'
lock = Lock()

request_manager = RequestManager(user_name, user_pswd, user_path, browser, host, main_id)
village_manager = VillageManager(request_manager, lock, main_id, farm_with, use_def_to_farm=True, t_limit_to_leave=4)
for i in range(10):
    farm_pv = village_manager.get_next_attacking_village()
    print(farm_pv)

