import time
import sys
import os
import re
from threading import Lock
from request_manager import  RequestManager
from village_management import VillageManager
from attack_management import AttackManager
from data_management import ReportBuilder,AttackReport
from map_management import Map

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
farm_with = (127591, 126583,)  #(127591, 126583)
t_limit = 4
observer_file = 'test_observer_data'


lock = Lock()
request_manager = RequestManager(user_name, user_pswd, browser, host, main_id, run_path, logfile, events_file)
village_manager = VillageManager(request_manager, lock, main_id, farm_with, events_file, t_limit_to_leave=t_limit)
report_builder = ReportBuilder(request_manager, lock, run_path)
map = Map(base_x, base_y, request_manager, lock, run_path, events_file, depth=2, mapfile='new_map')
attack_manager = AttackManager(request_manager, lock, village_manager, report_builder, map, observer_file, logfile, events_file)

num_pages = 8

def get_reports_from_table(reports_table):
    single_report_ptrn = re.compile(r'<input name="id_[\W\w]+?</tr>')
    reports_list = re.findall(single_report_ptrn, reports_table)
    #    reports_list = [x for x in reports_list if '(new)' in x]
    battle_reports = []
    for report in reports_list: # filter out all support/recon/red reports
        match = re.search(r'<img src[\W\w]+?(yellow)|(green)\.png', report)
        if match:
            battle_reports.append(report)

    return battle_reports

flushed_reports = []
for i in range(num_pages):
    report_page = request_manager.get_reports_page(from_page=i*12)
    battle_reports = get_reports_from_table(report_page)
    for report in battle_reports:
        html_report = report_builder.get_single_report(report)
        attack_report = AttackReport(html_report)
        flushed_reports.append(attack_report)


for report in flushed_reports:
    coords = report.coords
    if coords in attack_manager.attack_queue.villages:
        villa = attack_manager.attack_queue.villages[coords]
        print('Villa before update: ', villa)
        if not villa.last_visited or villa.last_visited < report.t_of_attack:
            villa.update_stats(report)
            attack_manager.attack_queue.villages[coords] = villa
            print('Villa after update: ', attack_manager.attack_queue.villages[coords])

attack_manager.attack_queue.update_villages_in_map()







#f = shelve.open('map')
#villages = f['villages']
#print(len(villages.items()))
#for coords, villa in villages.items():
#    print(villa)
#    for t, loot in villa.looted['per_visit']:
#        print(time.ctime(t), ': looted==>', loot)
#
#f.close()
