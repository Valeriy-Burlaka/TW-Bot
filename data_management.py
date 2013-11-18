__author__ = 'Troll'

import re
import time
import random


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

    def __init__(self, request_manager, lock):
        self.request_manager = request_manager  # instance of RequestManager
        self.lock = lock    # shared instance of Bot's lock

    def get_new_reports(self, reports_count):
        """
        Downloads new battle reports from server.
        Inits AttackReport objects from downloaded reports.
        Validates inited AttackReports (all fields are filled)
        Returns mapping {(x, y): AttackReport, ..}, where (x,y) =
        coordinates of attacked village.
        """
        new_reports = {}
        # 12 reports per page. e.g.: if there 25 new reports, request 1, 2 & 3 report pages.
        pages = reports_count / 12 if reports_count%12 == 0 else (reports_count / 12) + 1
        # (+1) is a hardcoded sanity check: new reports may be shifted from page by trade reports, etc.
        pages = int(pages) + 1
        for page in range(pages):
            reports_page = self.get_reports_page(page)
            battle_reports = self.get_reports_from_page(reports_page)
            for report_data in battle_reports:
                html_report, coords = self.get_single_report(report_data)
                attack_report = AttackReport(html_report)
                if attack_report.is_valid_report:
                #print("Created valid report for: {}".format(coords))
                    new_reports[coords] = attack_report
                else:
                    print("Invalid report on coords: {}".format(coords))

        return new_reports

    def get_reports_page(self, page):
        """
        Requests default (1st) report page from server.
        We assume that AttackObserver will trigger update of
        reports in time, so no new reports will be after 1st report page.
        """
        self.lock.acquire()
        reports_page = self.request_manager.get_reports_page(from_page=page*12)
        self.lock.release()
        reports_page_ptrn = re.compile(r'<table id="report_list"[\W\w]+?</table>')  # table with 12 reports
        match = re.search(reports_page_ptrn, reports_page)
        reports_page = match.group()
        return reports_page

    def get_reports_from_page(self, reports_page):
        """
        Extracts single reports from report table and filters out
        non-green/yellow reports (only green & yellow can contain info
        about looted & remaining village capacity.
        Returns list which contains HTML chunks, each with URL for single report.
        """
        single_report_ptrn = re.compile(r'<input name="id_[\W\w]+?</tr>')
        reports_list = re.findall(single_report_ptrn, reports_page)
        reports_list = [x for x in reports_list if '(new)' in x]    # get reports marked as "new"
        battle_reports = []
        for report in reports_list: # filter out all support/recon/red reports
            match = re.search(r'<img src[\W\w]+?(yellow)|(green)\.png', report)
            if match:
                battle_reports.append(report)

        return battle_reports

    def get_single_report(self, report):
        """
        Extracts report URL from given HTML and requests
        single report page from server. Returns HTML page
        of single attack report & coordinates of village that was attacked.
        """
        href_ptrn = re.compile(r'<a href="([\W\w]+?)">')
        coords_ptrn = re.compile(r'(\d{3})\|(\d{3})')
        url = re.search(href_ptrn, report)
        url = url.group(1)
        url = url.replace('&amp;', '&')
        coords = re.search(coords_ptrn, report)
        coords = (int(coords.group(1)), int(coords.group(2)))
        # Do not hit server too frequently
        time.sleep(random.random() * 5)
        self.lock.acquire()
        html_report = self.request_manager.get_report(url)
        self.lock.release()
        return html_report, coords


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
        self.is_valid_report = True
        self.build_report()

    def build_report(self):
        """
        Invokes each method that sets field and checks
        if self.is_valid_report is still True.
        Returns if any of fields was not set (non-valid battle report)
        """
        field_setters = [self.set_status, self.set_t_of_attack,
                         self.set_mines_level, self.set_capacities]
        for setter in field_setters:
            if self.is_valid_report:
                setter()
            else: return

    def set_status(self):
        match = re.search(r'/graphic/dots/(\w+).png', self.data)    # green, yellow
        if match:
            self.status = match.group(1)
        else: self.is_valid_report = False

    def set_t_of_attack(self):
        # "Nov 03, 2013  14:01:57"
        pattern = re.compile(r'(\w{3})\s(\d\d),\s(\d{4})\s\s(\d\d):(\d\d):(\d\d)')
        match = re.search(pattern, self.data)
        if match:
            str_t = match.group()
            struct_t = time.strptime(str_t, "%b %d, %Y %H:%M:%S")
            self.t_of_attack = round(time.mktime(struct_t))
        else: self.is_valid_report = False

    def set_mines_level(self):
        mines = ["Timber camp", "Clay pit", "Iron mine"]
        levels = []
        for mine in mines:
            search = r'{}\s<b>\WLevel\s(\d+)\W</b>'.format(mine) # "Barracks <b>(Level 4)</b>"
            match = re.search(search, self.data)
            if match:
                levels.append(int(match.group(1)))
            else:
                levels.append(0)

        self.mine_levels = levels

    def set_capacities(self):
        scouted = re.search(r'Resources scouted:[\w\W]+Buildings:', self.data)
        looted = re.search(r'Haul:[\w\W]+Publicize this report', self.data)

        def get_haul_amount(s_resources):
            # <span class="icon header stone"> </span>800
            wood_pattern = re.compile(r'wood[\W\w]{1,200}stone')
            clay_pattern = re.compile(r'stone[\W\w]{1,200}iron')
            iron_pattern = re.compile(r'iron[\W\w]+?</td>')
            i_amount = 0
            for ptrn in (wood_pattern, clay_pattern, iron_pattern,):
                match = re.search(ptrn, s_resources)
                if match:
                    s_resource = match.group()
                    # floats: "...wood"> </span>1 span class="grey">.</span>175"
                    amounts = re.findall(r'\d+', s_resource)
                    s_amount = ''
                    for s in amounts:
                        s_amount += s
                    i_amount += int(s_amount)
                else:
                    return

            return i_amount

        if scouted and looted:
            self.remaining_capacity = get_haul_amount(scouted.group())
            self.looted_capacity = get_haul_amount(looted.group())
        else:
            self.is_valid_report = False
            return
