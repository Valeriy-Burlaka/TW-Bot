import time
import sys
import os
import logging
import traceback
from threading import Lock
from request_manager import  RequestManager
from village_management import VillageManager
from attack_management import AttackManager
from data_management import ReportBuilder
from map_management import Map


def main(arguments):
    platform = sys.platform
    if platform not in ('linux', 'win32'):
        print("Sorry, but Bot doesn't like your OS"
              "(only Windows & Linux platforms are currently supported)")
        sys.exit(1)
    try:
        import settings
    except ImportError:
        print("Settings file was not found")
        sys.exit(1)

    logging_level = 10  # WARNING
    if len(arguments) > 1:
        numeric_log_level = getattr(logging, arguments[1].upper(), None)
        if isinstance(numeric_log_level, int):
            logging_level = numeric_log_level
        else:
            print("Received unknown logging level as first argument."
                  "Using WARNING level instead")

    logging.basicConfig(filename='log.txt', level=logging_level,
                        format='%(asctime)s: %(levelname)s: %(message)s',
                        datefmt='%d/%b/%Y %H:%M:%S %Z %z')
    runner = Runner(platform)
    try:
        runner.start()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception:
        print("Unexpected exception occurred. See error log for more details.")
        error_info = traceback.format_exception(*sys.exc_info())
        logging.critical(error_info)
    finally:
        runner.stop()
        sys.exit()


class Runner:
    def __init__(self, platform):
        self.platform = platform
        


# run_name = time.strftime("%d %b %H-%M-%S GMT", time.gmtime())
# run_path = os.path.join(sys.path[0], "bot_runs", run_name)
# if not os.path.exists(run_path):
#     os.makedirs(run_path)
#
# logfile = os.path.join(run_path, "errors_log.txt")
#
# lock = Lock()
#
# try:
#     request_manager = RequestManager(user_name, user_pswd, browser, host, main_id, run_path, logfile, events_file)
#     village_manager = VillageManager(request_manager, lock, main_id, farm_with, events_file, run_path,
#                                     use_def_to_farm=False, heavy_is_def=False, t_limit_to_leave=t_limit)
#     report_builder = ReportBuilder(request_manager, lock, run_path)
#
#     map = Map(base_x, base_y, request_manager, lock, run_path, events_file, depth=2, mapfile='new_map')
#     attack_manager = AttackManager(request_manager, lock, village_manager, report_builder, map,
#                                     observer_file, logfile, events_file, submit_id_numbers)
#
#     attack_manager.start()
#     time.sleep(3600 * 31)
#
#
#     attack_manager.stop()


if __name__ == '__main__':
    try:
        main(sys.argv)
    except SystemExit:
        print("Exiting now")
        os._exit(1)