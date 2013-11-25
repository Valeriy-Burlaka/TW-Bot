__author__ = 'Troll'


import time
import shelve
import re
import gzip
import os
from threading import Lock
from request_manager import RequestManager
#from attack_management import AttackManager, AttackObserver
from data_management import ReportBuilder, AttackReport
from map_management import Village
##
#reports_folder = 'test_html'
#reports = {}
#for report_name in os.listdir(reports_folder):
#    print(report_name)
#    if 'report' in report_name:
#        if 'page' not in report_name:
#            with open(os.path.join(reports_folder, report_name)) as f:
#                report_data = f.read()
#                attack_report = AttackReport(report_data)
#                reports[report_name] = attack_report
#
#for k, v in reports.items():
#    print(k, '=>', v)

#f_old = shelve.open('map')
#villages_old = f_old['villages']
#f_new = shelve.open('new_map')
#villages_new = {}
#for village in villages_old.values():
#    v_coords = village.coords
#    v_id = village.id
#    population = village.population
#    h_rates = village.h_rates
#    visit = village.last_visited
#    loot = village.looted
#    new_village = Village(v_coords, v_id, population)
#    new_village.bonus = village.bonus
#    new_village.mine_levels = village.mine_levels
#    new_village.h_rates = h_rates
#    new_village.last_visited = visit
#    new_village.looted = loot
#
#    villages_new[v_coords] = new_village
#
#f_new['villages'] = villages_new
#f_new.close()
#f_old.close()
#f_new = shelve.open('new_map')
#new_villages = f_new['villages']
#print(len(new_villages))
#for villa in new_villages.values():
#    print(villa)
#
#f_new.close()

with open(r'C:\Users\Troll\Documents\exercises\TW\clonned_bot\bot_runs\24 Nov 22-31-59 GMT\errors_log.txt') as f:
    for i in range(1000):
        print(f.readline())