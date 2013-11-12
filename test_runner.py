import time
import sys
from threading import Lock
from request_manager import  RequestManager
from attack_management import AttackManager
from data_management import ReportBuilder


lock = Lock()
request_manager = RequestManager()
report_builder = ReportBuilder(request_manager, lock)
am = AttackManager(211, 305, request_manager, report_builder, lock, farm_radius=18, queue_depth=15,
                    farm_frequency=4)
try:     
    am.start()
    time.sleep(18000)
    am.active = False
except KeyboardInterrupt:
    am.active = False
    sys.exit()