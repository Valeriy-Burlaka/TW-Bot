import sys
import re
import time
import logging
import traceback

from bs4 import BeautifulSoup as Soup


class ReportManager:
    """
    Helps to create AttackReport objects with the next
    methods:

    get_report_urls:
        takes HTML (string) of report page and
        returns list of URLs for each report on this page
    build_report:
        takes HTML (string) of single report and
        returns new AttackReport object.
    """

    def __init__(self, locale):
        self.locale = locale

    def get_report_urls(self, report_page, only_new=True):
        """
        Extracts URLs for each report on report page,
        """
        report_urls = []
        reports_raw_list = self._get_reports_from_page(report_page, only_new)
        for raw_report in reports_raw_list:
            report_url = self._get_single_report_url(raw_report)
            report_urls.append(report_url)
        return report_urls

    def build_report(self, report_page):
        report = AttackReport(report_page, locale=self.locale)
        return report

    @staticmethod
    def _get_reports_from_page(reports_page, only_new):
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

    @staticmethod
    def _get_single_report_url(report):
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


class AttackReport:
    """
    Extracts valuable data from a HTML string for
    a particular attack report.
    Neither xml.etree.ElementTree nor xml.dom.minidom
    in-build DOM parsers were able to parse TribalWars
    attack reports, so using regular expressions instead.
    """

    def __init__(self, str_html, locale):
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
        """
        Builds info about self from HTML string of report page
        """
        # Check if report has color status (green, blue, red, red_blue).
        # Otherwise we faced with non-battle report (trade/support)
        self._set_attack_status()
        if not self.status:
            return
        else:
            self.soup = Soup(self.data)

        if self.status == 'red':
            # No troops returned. No information collected.
            self._set_t_of_attack()
            self._set_target_coordinates()
            self.defended = True
            return
        else:
            field_setters = [self._set_target_coordinates,
                             self._set_t_of_attack,
                             self._set_defence,
                             self._set_building_levels,
                             self._set_capacities]
            for setter in field_setters:
                setter()

    def _set_attack_status(self):
        """
        Looks for color of image-icon that represents report
        status.
        Battle report statuses:
        red: all died, no information collected about target & battle
        blue, red_blue: there were only scoutes or all died except scouts
        (no haul).
        green, yellow: usual battle report (yellow = some casualties)
        """
        status_ptrn = re.compile(r'/graphic/dots/([\W\w]+?)\.png')
        match = re.search(status_ptrn, self.data)
        if match:
            self.status = match.group(1)

    def _set_target_coordinates(self):
        """
        Sets target coordinates
        """
        # span with report header (e.g. foo attacks barBs (220|317))
        try:
            target_element = self.soup.find(id='labelText')
            text = target_element.text
        except AttributeError:
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
            try:
                logging.warning("Unable to extract target coords with old-style"
                                "parsing strategy, using new-style instead")
                target_element = self.soup.find("span", class_="quickedit-label")
                text = target_element.text
            except AttributeError as e:
                with open('bad_report_data_coords.html', 'w') as f:
                    f.write(str(self.soup))
                raise e
        coords_ptrn = re.compile(r"(\d{3})\|(\d{3})")
        match = re.search(coords_ptrn, text)
        if match:
            self.coords = (int(match.group(1)), int(match.group(2)))
        else:
            # battle, but non-attack report (e.g. "support has been attacked")
            self.coords = (0, 0)    # set non-existing coordinates

    def _set_t_of_attack(self):
        if self.locale["dateformat"] == "abbreviated":
            pattern = re.compile(r"""(\w{3})\s  # abbreviated month name
                                     (\d{2}),\s  # decimal day
                                     (\d{4})\s{1,2}  # year
                                     (\d{2}):(\d{2}):(\d{2})  # hours-minutes-seconds
                                     # e.g: "Nov 03, 2013  14:01:57"
                                  """,
                                 re.VERBOSE)

            match = re.search(pattern, self.data)
            if match:
                str_t = match.group()
                struct_t = time.strptime(str_t, "%b %d, %Y %H:%M:%S")
                self.t_of_attack = round(time.mktime(struct_t))
        elif self.locale["dateformat"] == "numerical":
            pattern = re.compile(r"""(\d{2})/  # decimal day
                                     (\d{2})/  # decimal month
                                     (\d{4})\s{1,2}  # year
                                     (\d{2}):(\d{2}):(\d{2})  # hours-minutes-seconds
                                     # e.g: "07/03/2014 00:23:23"
                                  """,
                                 re.VERBOSE)
            match = re.search(pattern, self.data)
            if match:
                str_t = match.group()
                struct_t = time.strptime(str_t, "%d/%m/%Y %H:%M:%S")
                self.t_of_attack = round(time.mktime(struct_t))

    def _set_defence(self):
        """
        Simplified way to determine if village is protected:
        We look for table containing info about defender's troops
        in DOM and count cells with non-zero unit quantities.
        """
        defender_troops_table = self.soup.find(id="attack_info_def_units")
        # catch for a game response with corrupted data:
        try:
            defender_troops_quantity = defender_troops_table.findAll('tr')[1]
        except IndexError:
            with open('bad_report_data_troops.html', 'w') as f:
                f.write(str(self.soup))
            self.defended = False
            return
        # each unit has its own <td> cell. If unit count == 0, <td> class
        # will be "unit-item hidden"
        empty_slots = defender_troops_quantity.findAll("td", "unit-item hidden")
        if len(empty_slots) == 13:
            self.defended = False
        else:
            self.defended = True

    def _set_building_levels(self):
        """
        Looks for DOM element with id="attack_spy" (it will
        be there if attack was sent with scouts) and sets
        building levels.
        """
        level_name = self.locale["level_name"]
        espionage = self.soup.find(id="attack_spy")
        if espionage is not None:
            text = espionage.text
        else:
            text = ""
        mines = self.locale["mines"]
        mine_levels = []
        for mine in mines:
            level = self._get_building_level(text, mine, level_name)
            mine_levels.append(level)
            self.mine_levels = mine_levels
        storage = self.locale["storage"]
        self.storage_level = self._get_building_level(text, storage, level_name)
        wall = self.locale["wall"]
        self.wall_level = self._get_building_level(text, wall, level_name)

    @staticmethod
    def _get_building_level(text, building_name, level_name):
        """
        Parses input text to get building level.
        """
        search = r'{building}\s\W{level}\s(\d+)\W'.format(building=building_name,
                                                          level=level_name)
        match = re.search(search, text)
        if match:
            return int(match.group(1))
        else:
            # if building name is not found while village was
            # scouted, this means it's not constructed
            return 0

    def _set_capacities(self):
        """
        Sets information about resources amount that was looted
        & resources that remained in village.
        """
        # in report, if attack was sent with scout
        espionage = self.soup.find(id="attack_spy")
        if espionage is not None:
            text = str(espionage.findAll('tr')[0])
            remaining_capacity = self._get_haul_amount(text)
        else:
            # Since we went to attack w/o scout, mark the village
            # as completely looted.
            remaining_capacity = 0
        self.remaining_capacity = remaining_capacity
        # in report, if someone from troops sent remained alive
        attack_results = self.soup.find(id="attack_results")
        if attack_results is not None:
            text = str(attack_results.findAll('tr')[0])
            looted_capacity = self._get_haul_amount(text)
        else:
            # Jimmy is dead or Jimmy was just a scout: nothing was looted
            looted_capacity = 0
        self.looted_capacity = looted_capacity

    @staticmethod
    def _get_haul_amount(s_resources):
        """
        Parses input string to get resources amount (looted &
        scouted).
        Steps are a bit unclear: this is due to the way TW
        presents scouted & looted resources (values >3 digits
        are separated by dots between <span>'s, no 'total' for
        scouted)
        """
        # grab the chunk which contains loot info for particular
        # resource.
        wood_pattern = re.compile(r'wood[\W\w]{1,200}stone')
        clay_pattern = re.compile(r'stone[\W\w]{1,200}iron')
        iron_pattern = re.compile(r'iron[\W\w]+?</td>')
        i_amount = 0
        for ptrn in (wood_pattern, clay_pattern, iron_pattern,):
            match = re.search(ptrn, s_resources)
            if match:
                s_resource = match.group()
                # floats:
                amounts = re.findall(r'\d+', s_resource)
                s_amount = ''
                for s in amounts:
                    s_amount += s
                i_amount += int(s_amount)
            else:
                return

        return i_amount

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
