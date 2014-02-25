import re
import time

from bs4 import BeautifulSoup as Soup


class ReportManager:
    """
    Component responsible for building AttackReport objects
    from new game reports. Collects coordinates & report URLs
    for all "new" reports from report overview page and then
    requests each report by URL.
    Neither xml.etree.ElementTree nor xml.dom.minidom
    in-build DOM parsers were able to parse TribalWars report page/
    attack reports, so using regular expressions instead.
    """

    def __init__(self, locale):
        self.locale = locale

    def get_report_urls(self, report_page, only_new=True):
        report_urls = []
        reports_raw_list = self._get_reports_from_page(report_page, only_new)
        for raw_report in reports_raw_list:
            report_url = self._get_single_report_url(raw_report)
            report_urls.append(report_url)
        return report_urls

    def build_report(self, report_page):
        report = AttackReport(report_page, locale=self.locale)
        return report

    def _get_reports_from_page(self, reports_page, only_new):
        """
        Extracts single reports data from reports page.
        Returns list of HTML-chunks, containing actual URLs
        for single reports.
        """
        single_report_ptrn = re.compile(r'<input name="id_[\W\w]+?</tr>')
        reports_list = re.findall(single_report_ptrn, reports_page)
        if only_new:
            # get reports marked as "new"
            reports_list = [x for x in reports_list if '(new)' in x]
        return reports_list

    def _get_single_report_url(self, report):
        """
        Extracts report URL from given HTML and requests
        single report page from server. Returns HTML page
        of single attack report.
        """
        href_ptrn = re.compile(r'<a href="([\W\w]+?)">')
        url = re.search(href_ptrn, report)
        url = url.group(1)
        url = url.replace('&amp;', '&')
        return url

    def _get_reports_page(self, page):
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


class AttackReport:
    """
    Extracts valuable data from a HTML string for
    a particular attack report.
    Neither xml.etree.ElementTree nor xml.dom.minidom
    in-build DOM parsers were able to parse TribalWars
    attack reports, so using regular expressions instead.
    """

    def __init__(self, str_html, locale=None):
        self.data = str_html
        self.locale = locale
        self.status = None
        self.coords = None
        self.t_of_attack = None
        self.defended = None
        self.mine_levels = None
        self.remaining_capacity = None
        self.looted_capacity = None
        self.storage_level = None
        self.wall_level = None
        self.soup = None
        self.build_report()

    def build_report(self):
        # check if report has color status (green, blue, etc.).
        # Otherwise we faced with non-battle report (supply/support)
        self.set_attack_status()
        if not self.status:
            return
        else:
            self.soup = Soup(self.data)

        if self.status == 'red':  # No troops returned. No information collected.
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
        target_element = self.soup.find(id='labelText')
        text = target_element.text
        coords_ptrn = re.compile(r"(\d{3})\|(\d{3})")
        match = re.search(coords_ptrn, text)
        if match:
            self.coords = (int(match.group(1)), int(match.group(2)))
        else:
            # battle, but non-attack report (e.g. "support has been attacked")
            self.coords = (0, 0)    # set non-existing coordinates

    def set_t_of_attack(self):
        # e.g: "Nov 03, 2013  14:01:57"
        pattern = re.compile(r"""(\w{3})\s  # abbreviated month name
                                 (\d{2}),\s  # decimal day
                                 (\d{4})\s{1,2}  # year
                                 (\d{2}):(\d{2}):(\d{2})  # hours-minutes-seconds
                              """,
                             re.VERBOSE)

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
        defender_troops_table = self.soup.find(id="attack_info_def_units")
        defender_troops_quantity = defender_troops_table.findAll('tr')[1]
        # each unit has its own <td> cell. If unit count == 0, <td> class
        # will be "unit-item hidden"
        empty_slots = defender_troops_quantity.findAll("td", "unit-item hidden")
        if len(empty_slots) == 13:
            self.defended = False
        else:
            self.defended = True

    def set_mines_level(self):
        # buildings_table = self.soup.find(id="attack_spy")
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


