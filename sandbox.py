__author__ = 'Troll'


import time
from threading import Lock
from request_manager import  RequestManager
from attack_management import AttackManager
from data_management import ReportBuilder


lock = Lock()
request_manager = RequestManager()
report_builder = ReportBuilder(request_manager, lock)
am = AttackManager(211, 305, request_manager, report_builder, lock, farm_radius=18, queue_depth=15,
                    farm_frequency=4, capacity_threshold=1800)
am.start()
time.sleep(25200)
am.active = False













