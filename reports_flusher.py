import re
from threading import Lock
from request_manager import  RequestManager
from village_management import VillageManager
from attack_management import AttackManager
from data_management import ReportBuilder, AttackReport
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
num_pages = 8

request_manager = RequestManager(user_name, user_pswd, user_path, browser, host, main_id)
village_manager = VillageManager(request_manager, lock, main_id, farm_with, t_limit_to_leave=t_limit)
report_builder = ReportBuilder(request_manager, lock)
map = Map(base_x, base_y, request_manager, lock, depth=3, mapfile='map')

attack_manager = AttackManager(request_manager, lock, village_manager, report_builder, map, observer_file)


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

flushed_reports = {}
for i in range(num_pages):
    report_page = request_manager.get_reports_page(from_page=i*12)
    battle_reports = get_reports_from_table(report_page)
    for report in battle_reports:
        html_report, coordinates = report_builder.get_single_report(report)
        attack_report = AttackReport(html_report)
        if attack_report.is_valid_report:
            flushed_reports[coordinates] = attack_report
        else:
            with open('bad_reports/{coords}_invalid_report.html'.format(coords=coordinates), 'w') as f:
                f.write(html_report)

for coords, report in flushed_reports.items():
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
