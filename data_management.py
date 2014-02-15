import re
import os
import time
import random
import sys
import traceback
import logging


class ReportBuilder:
    """
    Component responsible for building AttackReport objects
    from new game reports. Collects coordinates & report URLs
    for all "new" reports from report overview page and then
    requests each report by URL.
    Neither xml.etree.ElementTree nor xml.dom.minidom
    in-build DOM parsers were able to parse TribalWars report page/
    attack reports, so using regular expressions instead.
    """

    def __init__(self, request_manager, lock, run_path):
        self.request_manager = request_manager  # instance of RequestManager
        self.lock = lock    # shared instance of Bot's lock
        self.report_path = os.path.join(run_path, "run_reports")
        self.report_errors = os.path.join(self.report_path, "report_errors.txt")
        if not os.path.exists(self.report_path): os.mkdir(self.report_path)

    def get_new_reports(self, reports_count):
        """
        Downloads new battle reports from server.
        Inits AttackReport objects from downloaded reports.
        Validates inited AttackReports (all fields are filled)
        Returns mapping {(x, y): AttackReport, ..}, where (x,y) =
        coordinates of attacked village.
        """
        new_reports = []
        # 12 reports per page. e.g.: if there 25 new reports,
        # request 1, 2 & 3 report pages.
        pages = reports_count / 12 if reports_count%12 == 0 else (reports_count / 12) + 1
        # (+1) is a hardcoded sanity check: new reports may be
        # shifted from page by trade reports, etc.
        pages = int(pages) + 1
        for page in range(pages):
            reports_page = self.get_reports_page(page)
            battle_reports = self.get_reports_from_page(reports_page)
            for report_data in battle_reports:
                try:
                    html_report = self.get_single_report(report_data)
                    attack_report = AttackReport(html_report)
                except TypeError:
                    error_info = traceback.format_exception(*sys.exc_info())
                    logging.error(error_info)
                    # Hunting bug with TypeError raised on some game reports
                    # Save problem report data to a local file for further
                    # investigation
                    filename = "Type_exception_report_data_" \
                               "{t}.html".format(t=round(time.time()))
                    filename = os.path.join(self.report_path, filename)
                    with open(filename, 'w') as f:
                        f.write(report_data)
                except AttributeError:
                    error_info = traceback.format_exception(*sys.exc_info())
                    logging.error(error_info)
                    filename = "Attribute_exception_report_" \
                               "{t}.html".format(t=round(time.time()))
                    filename = os.path.join(self.report_path, filename)
                    with open(filename, 'w') as f:
                        f.write(html_report)

                if not attack_report.status:    # skip non-battle reports
                    continue
                elif attack_report.status == 'red' or attack_report.status == 'red_blue':
                    filename = "critical_report_" \
                               "{t}.html".format(t=attack_report.t_of_attack)
                    filepath = os.path.join(self.report_path, filename)
                    with open(filepath, 'w') as f:
                        f.write(attack_report.data)
                elif attack_report.status == 'yellow':
                    filename = "warning_report_" \
                               "{t}.html".format(t=attack_report.t_of_attack)
                    filepath = os.path.join(self.report_path, filename)
                    with open(filepath, 'w') as f:
                        f.write(attack_report.data)

                new_reports.append(attack_report)

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
        Extracts single reports from report table.
        Returns list which contains HTML chunks, each with URL for single report.
        """
        single_report_ptrn = re.compile(r'<input name="id_[\W\w]+?</tr>')
        reports_list = re.findall(single_report_ptrn, reports_page)
        reports_list = [x for x in reports_list if '(new)' in x]    # get reports marked as "new"
        return reports_list

    def get_single_report(self, report):
        """
        Extracts report URL from given HTML and requests
        single report page from server. Returns HTML page
        of single attack report.
        """
        href_ptrn = re.compile(r'<a href="([\W\w]+?)">')
        url = re.search(href_ptrn, report)
        url = url.group(1)
        url = url.replace('&amp;', '&')
        # Do not hit server too frequently
        time.sleep(random.random() * 2)
        self.lock.acquire()
        html_report = self.request_manager.get_report(url)
        self.lock.release()
        return html_report


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
        self.status = None
        self.coords = None
        self.t_of_attack = None
        self.defended = None
        self.mine_levels = None
        self.remaining_capacity = None
        self.looted_capacity = None
        self.storage_level = None
        self.wall_level = None
        self.build_report()

    def build_report(self):
        # check if report has color status (green, blue, etc.).
        # Otherwise we faced with non-battle report (supply/support)
        self.set_attack_status()
        if not self.status:
            return
        elif self.status == 'red':  # No troops returned. No information collected.
            self.set_t_of_attack()
            self.set_target_coordinates()
            self.defended = True
            return
        else:
            field_setters = [self.set_target_coordinates, self.set_t_of_attack, self.set_defence,
                             self.set_mines_level, self.set_capacities, self.set_storage_level,
                             self.set_wall_level]
            for setter in field_setters:
                setter()

    def set_attack_status(self):
        status_ptrn = re.compile(r'/graphic/dots/([\W\w]+?)\.png')
        match = re.search(status_ptrn, self.data)
        if match:
            self.status = match.group(1)

    def set_target_coordinates(self):
        coords_ptrn = re.compile(r"attacks[\w\W]+?(\d{3})\|(\d{3})")
        match = re.search(coords_ptrn, self.data)
        # Didn't place NoneType check for match here:
        # 1. We suppose all non-battle reports are filtered out
        # 2. If Bot has flushed reports of kind "Bad guy attacks Player", player's
        # coordinates will not be found in list of farmed villages & just skipped.
        if match:
            self.coords = (int(match.group(1)), int(match.group(2)))
        else: # battle, but non-attack report (e.g. "support has been attacked"
            self.coords = (0, 0)    # set non-existing coordinates

    def set_t_of_attack(self):
        # "Nov 03, 2013  14:01:57"
        pattern = re.compile(r'(\w{3})\s(\d\d),\s(\d{4})\s\s(\d\d):(\d\d):(\d\d)')
        match = re.search(pattern, self.data)
        if match:
            str_t = match.group()
            struct_t = time.strptime(str_t, "%b %d, %Y %H:%M:%S")
            self.t_of_attack = round(time.mktime(struct_t))

    def set_defence(self):
        """
        Simplified way to determine if village is protected:
        1. We extract chunk of HTML with table of defender's units.
        2. If unit count == 0, it is stored in "class='unit-item hidden'"
        3. There are 13 types of units, so if len of re.findall result != 13,
        there is some defence and it's better to save this report
        for human evaluation.
        """
        defender_section_ptrn = re.compile(r'Defender[\W\w]+?Quantity([\W\w]+?)</tr>')
        match = re.search(defender_section_ptrn, self.data)
        if match:
            defender_troops = match.group(1)
            empty_slots = re.findall(r'unit-item hidden', defender_troops)
            if len(empty_slots) == 13:
                self.defended = False
            else:
                self.defended = True

    def set_mines_level(self):
        mines = ["Timber camp", "Clay pit", "Iron mine"]
        levels = []
        for mine in mines:
            # "Barracks <b>(Level 4)</b>"
            search = r'{}\s<b>\WLevel\s(\d+)\W</b>'.format(mine)
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

        if scouted:
            self.remaining_capacity = get_haul_amount(scouted.group())
        # Since we went to attack w/o scout, mark the village
        # as completely looted.
        else:
            self.remaining_capacity = 0
        if looted:
            self.looted_capacity = get_haul_amount(looted.group())
        else:   # It was a scout attack, nothing was looted
            self.looted_capacity = 0

    def set_storage_level(self):
        storage_ptrn = re.compile(r"Warehouse\s<b>\WLevel\s(\d+)\W</b>")
        match = re.search(storage_ptrn, self.data)
        if match:
            self.storage_level = int(match.group(1))

    def set_wall_level(self):
        wall_ptrn = re.compile(r"Wall\s<b>\WLevel\s(\d+)\W</b>")
        match = re.search(wall_ptrn, self.data)
        if match:
            self.wall_level = int(match.group(1))
        else:
            self.wall_level = 0

    def __str__(self):
        str_report = "AttackReport: \t\t  status => {status}, coords => " \
                     "{coords}, attack time => {t},\n\
                      defended? => {defence}, mines => {mines}, " \
                     "scouted => {remaining}, haul => {loot},\n\
                      storage => {storage}, " \
                     "wall => {wall}".format(status=self.status,
                                             coords=self.coords,
                                             t=time.ctime(self.t_of_attack),
                                             defence=self.defended,
                                             mines=self.mine_levels,
                                             remaining=self.remaining_capacity,
                                             loot=self.looted_capacity,
                                             storage=self.storage_level,
                                             wall=self.wall_level)

        return str_report

    def __repr__(self):
        return self.__str__()


