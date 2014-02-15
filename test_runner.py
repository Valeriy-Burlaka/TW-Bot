import time
import sys
import os
import traceback
from threading import Lock
from request_manager import  RequestManager
from village_management import VillageManager
from attack_management import AttackManager
from data_management import ReportBuilder, write_log_message
from map_management import Map



run_name = time.strftime("%d %b %H-%M-%S GMT", time.gmtime())
run_path = os.path.join(sys.path[0], "bot_runs", run_name)
if not os.path.exists(run_path):
    os.makedirs(run_path)

logfile = os.path.join(run_path, "errors_log.txt")

lock = Lock()

try:
    request_manager = RequestManager(user_name, user_pswd, browser, host, main_id, run_path, logfile, events_file)
    village_manager = VillageManager(request_manager, lock, main_id, farm_with, events_file, run_path,
                                    use_def_to_farm=False, heavy_is_def=False, t_limit_to_leave=t_limit)
    report_builder = ReportBuilder(request_manager, lock, run_path)

    map = Map(base_x, base_y, request_manager, lock, run_path, events_file, depth=2, mapfile='new_map')
    attack_manager = AttackManager(request_manager, lock, village_manager, report_builder, map,
                                    observer_file, logfile, events_file, submit_id_numbers)

    #new_reports = report_builder.get_new_reports(12 * 9)
    #attack_manager.attack_queue.update_villages(new_reports)
    #attack_manager.attack_queue.update_villages_in_map()
    attack_manager.start()
    time.sleep(3600 * 31)
except KeyboardInterrupt:
    print("Interrupted by user")
except Exception:
    error_info = traceback.format_exception(*sys.exc_info())
    str_info = "Unexpected exception occurred. Error information: {info}".format(info=error_info)
    write_log_message(logfile, str_info)
finally:
    attack_manager.stop()




