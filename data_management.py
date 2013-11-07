__author__ = 'Troll'

import re
import time


class ReportBuilder:
    """
    Component responsible for building AttackReport objects
    for new game reports. Collects coordinates & report URLs
    for all "new" reports from report overview page and then
    requests each report by URL.
    Neither xml.etree.ElementTree nor xml.dom.minidom
    in-build DOM parsers were able to parse TribalWars report page/
    attack reports, so using regular expressions instead.
    """

    def __init__(self, request_manager):
        self.request_manager = request_manager  # instance of RequestManager

    def get_reports_table(self):
        reports_page = self.request_manager.get_reports_page()
        report_table_ptrn = re.compile(r'<table id="report_list"[\W\w]+?</table>')  # table with 12 reports
        match = re.search(report_table_ptrn, reports_page)
        reports_table = match.group()
        return reports_table

    def get_reports_from_table(self, reports_table):
        single_report_ptrn = re.compile(r'<input name="id_[\W\w]+?</tr>')
        reports_list = re.findall(single_report_ptrn, reports_table)
        reports_list = [x for x in reports_list if '(new)' in x]    # get reports marked as "new"
        battle_reports = []
        for report in reports_list: # filter out all support/recon/red reports
            match = re.search(r'<img src[\W\w]+?(yellow)|(green)\.png', report)
            if match:
                battle_reports.append(report)

        return battle_reports

    def get_single_report(self, report):
        href_ptrn = re.compile(r'<a href=[\W\w]+?>')
        coords_ptrn = re.compile(r'(\d{3})\|(\d{3})')
        url = re.search(href_ptrn, report)
        url = url.group()
        coords = re.search(coords_ptrn, report)
        coords = (int(coords.group(1)), int(coords.group(2)))
        html_report = self.request_manager.get_report(url)
        return html_report, coords

    def get_new_reports(self):
        new_reports = {}
        reports_table = self.get_reports_table()
        battle_reports = self.get_reports_from_table(reports_table)
        for report_data in battle_reports:
            html_report, coords = self.get_single_report(report_data)
            new_reports[coords] = AttackReport(html_report)

        return new_reports


class AttackReport:
    """
    Extracts valuable data from a HTML string for
    a particular attack report.
    Neither xml.etree.ElementTree nor xml.dom.minidom
    in-build DOM parsers were able to parse TribalWars
    attack reports, so using regular expressions instead.
    """

    def __init__(self, str_html):
        self.data = str_html
        self.build_report()

    def build_report(self):
        self.set_status()
        self.set_t_of_attack()
        self.set_mines_level()
        self.set_capacities()

    def set_status(self):
        match = re.search(r'/graphic/dots/(\w+).png', self.data)    # green, yellow
        self.status = match.group(1)

    def set_t_of_attack(self):
        months = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5,
                  "Jun":6, "Jul":7, "Aug":8, "Sep":9, "Oct":10,
                  "Nov":11, "Dec":12}

        # "Nov 03, 2013  14:01:57"
        pattern = re.compile(r'(\w{3})\s(\d\d),\s(\d{4})\s\s(\d\d):(\d\d):(\d\d)')
        match = re.search(pattern, self.data)
        month = months[match.group(1)]
        day = int(match.group(2))
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        second = int(match.group(6))

        struct_t = time.struct_time(
            (year, month, day, hour, minute, second, 0, 0, 0))
        self.t_of_attack = round(time.mktime(struct_t))

    def set_mines_level(self):
        mines = ["Timber camp", "Clay pit", "Iron mine"]
        levels = []
        for mine in mines:
            search = r'{}\s<b>\WLevel\s(\d)\W</b>'.format(mine) # "Barracks <b>(Level 4)</b>"
            match = re.search(search, self.data)
            levels.append(int(match.group(1)))
        self.mine_levels = levels

    def set_capacities(self):
        scouted = re.search(r'Resources scouted:[\w\W]+Buildings:', self.data).group()
        looted = re.search(r'Haul:[\w\W]+Publicize this report', self.data).group()

        def get_haul_amount(s_resources):
            # <span class="icon header stone"> </span>800
            wood_pattern = re.compile(r'wood[\W\w]{1,200}stone')
            clay_pattern = re.compile(r'stone[\W\w]{1,200}iron')
            iron_pattern = re.compile(r'iron[\W\w]+?</td>')
            i_amount = 0
            for ptrn in (wood_pattern, clay_pattern, iron_pattern,):
                match = re.search(ptrn, s_resources)
                s_resource = match.group()
                # floats: "...wood"> </span>1 span class="grey">.</span>175"
                amounts = re.findall(r'\d+', s_resource)
                s_amount = ''
                for s in amounts:
                    s_amount += s
                i_amount += int(s_amount)
            return i_amount

        self.remaining_capacity = get_haul_amount(scouted)
        self.looted_capacity = get_haul_amount(looted)