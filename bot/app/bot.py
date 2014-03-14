import os
import sys
import time
import random
import logging
import traceback
from threading import Thread

import settings
from bot.app import locale
from bot.libs.map_tools import MapParser, MapMath
from bot.libs.common_tools import CookiesExtractor
from bot.libs.request_management import RequestManager
from bot.libs.village_management import VillageManager, EmptyVillage
from bot.libs.attack_management import AttackManager, AttackHelper
from bot.libs.report_management import ReportManager


class Bot(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.map_parser = MapParser()
        self.request_manager = None
        self.village_manager = None
        self.report_manager = None
        self.attack_manager = None
        self.attack_helper = None
        self.locale = None
        self.set_locale()
        self.setup_request_manager()
        self.setup_village_manager()
        self.setup_attack_manager()
        self.setup_report_manager()
        self.setup_attack_helper()
        self.active = False
        self.in_cycle = False

    def setup_request_manager(self):
        ce = CookiesExtractor()
        initial_cookies = ce.get_initial_cookies(run_path=settings.DATA_FOLDER,
                                                 browser_name=settings.BROWSER,
                                                 host=settings.HOST,
                                                 names=['cid', 'sid', 'mobile'])
        request_manager = RequestManager(host=settings.HOST,
                                         initial_cookies=initial_cookies,
                                         main_id=settings.MAIN_VILLAGE_ID,
                                         locale=self.locale,
                                         con_attempts=5,
                                         reconnect=True,
                                         username=settings.USER,
                                         password=settings.PASSWORD,
                                         antigate_key=settings.ANTIGATE_KEY)
        self.request_manager = request_manager

    def setup_village_manager(self):
        storage_filename = os.path.join(settings.DATA_FOLDER, settings.DATA_FILE)
        village_manager = VillageManager(storage_type=settings.DATA_TYPE,
                                         storage_name=storage_filename)
        overviews_html = self._get_overviews_screen()
        village_manager.build_player_villages(overviews_html)
        player_villages = village_manager.get_player_villages()
        farming_centers = list(player_villages.values())
        map_data = self._get_map_data(distinct_farming_centers=farming_centers,
                                      map_depth=2)
        village_manager.build_target_villages(map_data=map_data,
                                              trusted_targets=settings.TRUSTED_TARGETS,
                                              untrusted_targets=settings.UNTRUSTED_TARGETS,
                                              server_speed=settings.HOST_SPEED)
        if settings.FARM_WITH:
            farm_with = settings.FARM_WITH
        else:
            farm_with = player_villages.keys()
        for pv_id in farm_with:
            self._get_village_overview(pv_id)
            train_screen = self._get_train_screen(pv_id)
            village_manager.set_farming_village(attacker_id=pv_id,
                                                train_screen_html=train_screen,
                                                use_def_to_farm=settings.USE_DEF_TO_FARM,
                                                heavy_is_def=settings.HEAVY_IS_DEF)

        self.village_manager = village_manager

    def setup_attack_manager(self):
        storage_filename = os.path.join(settings.DATA_FOLDER, settings.DATA_FILE)
        attack_manager = AttackManager(storage_type=settings.DATA_TYPE,
                                       storage_name=storage_filename)
        targets = self.village_manager.get_attack_targets()
        attack_manager.build_attack_queue(target_villages=targets,
                                          farm_frequency=settings.FARM_FREQUENCY)
        self.attack_manager = attack_manager

    def setup_report_manager(self):
        self.report_manager = ReportManager(locale=self.locale)

    def setup_attack_helper(self):
        rally_screen = self._get_rally_overview(settings.MAIN_VILLAGE_ID)
        attack_helper = AttackHelper()
        attack_helper.set_confirmation_token(rally_point_html=rally_screen)
        self.attack_helper = attack_helper

    def run(self):
        self.active = True
        now = time.mktime(time.gmtime())
        end = now + settings.FARM_DURATION * 3600
        try:
            while self.active:
                self.attack_cycle()
                self.active = time.mktime(time.gmtime()) < end
        except AttributeError:
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
        except TypeError:
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
        except KeyError:
            error_info = traceback.format_exception(*sys.exc_info())
            logging.error(error_info)
        except Exception:
            print("Unexpected exception occurred. See error log for details.")
            error_info = traceback.format_exception(*sys.exc_info())
            logging.critical(error_info)

    def stop(self):
        self.active = False
        self._clean_up()

    def attack_cycle(self):
        self.in_cycle = True
        new_arrivals = self.attack_manager.get_new_arrivals()
        if new_arrivals:
            new_reports = self.get_new_reports(new_arrivals)
            self.attack_manager.update_attack_targets(new_reports)

        new_returns = self.attack_manager.get_new_returns()
        if new_returns:
            for pv_id in new_returns:
                train_screen = self._get_train_screen(pv_id)
                self.village_manager.refresh_village_troops(pv_id, train_screen)

        next_attacker = self.village_manager.get_next_attacking_village()
        if not next_attacker:
            # any of player's villages cannot attack
            if not settings.DEBUG:
                time.sleep(random.random() * 20)
                return

        attacker_id = next_attacker.id
        next_target = self.attack_manager.\
            get_next_attack_target(next_attacker=next_attacker,
                                   t_limit_to_leave=settings.T_LIMIT_TO_LEAVE,
                                   insert_spy=True)
        if not next_target:
            # given attacker cannot attack any of its targets
            self.village_manager.disable_farming_village(attacker_id)
            event_msg = "Disabling player's village:{id}".format(id=attacker_id)
            logging.info(event_msg)
            if not settings.DEBUG:
                time.sleep(random.random() * 10)
                return

        troops_to_send, t_on_road, target_coords = \
            next_target[0], next_target[1], next_target[2]
        t_of_attack = self.send_attack(attacker_id, coords=target_coords,
                                       troops=troops_to_send)
        logging.info("Time of the last attack: {}".format(t_of_attack))
        if t_of_attack:
            self.attack_manager.register_attack(attacker_id=attacker_id,
                                                target_coords=target_coords,
                                                t_of_attack=t_of_attack,
                                                t_on_the_road=t_on_road)
            self.village_manager.update_troops_count(attacker_id, troops_to_send)
            event_msg = "Attack sent at: {t1} from: {s} to: {c}. " \
                        "Troops: {tr}".format(t1=t_of_attack, s=attacker_id,
                                              c=target_coords, tr=troops_to_send)

            logging.info(event_msg)
        if not settings.DEBUG:
            time.sleep(random.random() * 5)
        self.in_cycle = False

    def get_new_reports(self, new_arrivals):
        new_battle_reports = []
        # 12 reports on 1 page
        report_pages = new_arrivals // 12
        # sanity check: reports may be shifted due to user actions
        # (trade, support, etc.)
        report_pages += 1
        for report_page in range(report_pages):
            from_page_param = report_page * 12
            html_report_page = self._get_reports_page(from_page_param)
            report_urls = self.report_manager.get_report_urls(html_report_page)
            for report_url in report_urls:
                html_report = self._get_report(report_url)
                attack_report = self.report_manager.build_report(html_report)
                if attack_report.status is not None:
                    if attack_report.status in ['red', 'red_blue']:
                        # fill with specific actions: save bad report, etc.
                        pass
                    new_battle_reports.append(attack_report)
        return new_battle_reports

    def send_attack(self, attacker_id, coords, troops):
        self._get_rally_overview(attacker_id)
        confirm_data = self.attack_helper.get_confirmation_data(coords, troops)
        confirm_response = self._post_confirmation(attacker_id, confirm_data)
        # Confirmation may be unsuccessful, if there were
        # no enough troops in village (e.g. due to user-sent attacks)
        try:
            attack_data = self.attack_helper.get_attack_data(coords, troops, confirm_response)
            csrf = self.attack_helper.get_csrf_token(confirm_response)
        except AttributeError:
            train_screen = self._get_train_screen(attacker_id)
            self.village_manager.refresh_village_troops(attacker_id, train_screen)
            return
        t_of_attack = self._post_attack(attacker_id, csrf, attack_data)
        return t_of_attack

    def set_locale(self):
        lang = settings.HOST[:2]
        if lang == 'us':
            lang = 'en'
        self.locale = locale.LOCALE[lang]

    def _clean_up(self):
        self.attack_manager.save_registered_attacks()
        recent_targets = self.attack_manager.get_recent_targets_info()
        self.village_manager.update_villages_in_storage(recent_targets)

    def _get_overviews_screen(self):
        if not settings.DEBUG:
            time.sleep(random.random())
        resp = self.request_manager.get_overviews_screen()
        return resp['response_text']

    def _get_map_overview(self, village_id, x, y):
        if not settings.DEBUG:
            time.sleep(random.random())
        resp = self.request_manager.get_map_overview(village_id=village_id, x=x, y=y)
        return resp['response_text']

    def _get_village_overview(self, village_id):
        if not settings.DEBUG:
            time.sleep(random.random())
        resp = self.request_manager.get_village_overview(village_id=village_id)
        return resp['response_text']

    def _get_train_screen(self, village_id):
        if not settings.DEBUG:
            time.sleep(random.random() * 2)
        resp = self.request_manager.get_train_screen(village_id=village_id)
        return resp['response_text']

    def _get_rally_overview(self, village_id):
        if not settings.DEBUG:
            time.sleep(random.random() * 2)
        resp = self.request_manager.get_rally_overview(village_id=village_id)
        return resp['response_text']

    def _get_reports_page(self, from_page):
        if not settings.DEBUG:
            time.sleep(random.random())
        resp = self.request_manager.get_reports_page(from_page=from_page)
        return resp['response_text']

    def _get_report(self, report_url):
        if not settings.DEBUG:
            time.sleep(random.random())
        resp = self.request_manager.get_report(url=report_url)
        return resp['response_text']

    def _post_confirmation(self, attacker_id, confirm_data):
        # User hits in fields to select troops to send
        if not settings.DEBUG:
            time.sleep(random.random() * 3)
        resp = self.request_manager.post_confirmation(village_id=attacker_id,
                                                               post_data=confirm_data)
        return resp['response_text']

    def _post_attack(self, attacker_id, csrf, request_data):
        # User just hits OK button
        if not settings.DEBUG:
            time.sleep(random.random())
        resp = self.request_manager.post_attack(village_id=attacker_id,
                                                csrf=csrf,
                                                post_data=request_data)
        return resp['response_time']

    def _get_map_data(self, distinct_farming_centers, map_depth):
        """
        Tries to retrieve distinct sectors data for given
        farming centers.
        Takes map_depth parameter which allows to get additional
        sectors_data recursively.
        That is, if map_depth=1, sectors_data will be retrieved only once
        (using farming center as a base).
        If map_depth=2, additional sectors_data will be retrieved for "corners"
        of 1st-level sectors_data, and so on.
        (Note: Sectors data will be retrieved at least once (e.g. with zero/negative
        initial value of map_depth).

        Merges data from all retrieved sectors and returns dictionary
        of all found villages data in area: {(x,y): [village_data, ..], ...}
        """
        map_depth -= 1
        map_data = {}
        while distinct_farming_centers:  # list of farming centers
            check_center = distinct_farming_centers[0]
            center_coords = check_center.coords
            center_x, center_y = center_coords[0], center_coords[1]
            center_id = check_center.id
            map_overview_html = self._get_map_overview(center_id, center_x, center_y)

            event_msg = "Retrieving map data from ({x},{y}) base point." \
                        "Map depth={depth}".format(x=center_x, y=center_y, depth=map_depth)
            logging.debug(event_msg)

            sectors_data = self.map_parser.collect_sector_data(map_overview_html)
            distinct_farming_centers = self._filter_distinct_centers(center_coords,
                                                                     distinct_farming_centers,
                                                                     sectors_data)
            area_data = self._merge_sectors_data(sectors_data)
            if map_depth > 0:
                area_coords = area_data.keys()
                area_corners = MapMath.get_area_corners(area_coords)

                event_msg = "Calculated the next area corners: {}".format(area_corners)
                logging.debug(event_msg)

                for corner in area_corners:
                    # area_data[(x, y)] - village data, 0 index = str(village_id)
                    corner_id = int(area_data[corner][0])
                    centers = [EmptyVillage(corner_id, corner)]
                    # Delay between "user" requests of map overview
                    if not settings.DEBUG:
                        time.sleep(random.random() * 6)
                    area_data.update(self._get_map_data(centers, map_depth))

            map_data.update(area_data)

        return map_data

    @staticmethod
    def _filter_distinct_centers(current_coords, centers, sectors_data):
        """
        Checks to which sector current attacker belongs and
        sorts out all attackers that also belong to the same sector.
        Returns a list of attacking centers that are not "neighbors"
        of a given attacker.
        """
        distinct_centers = []
        for sector in sectors_data:
            if current_coords in sector:
                for center in centers:
                    if center.coords not in sector:
                        distinct_centers.append(center)
        return distinct_centers

    @staticmethod
    def _merge_sectors_data(sectors_data):
        """
        Merges all given sectors to one area dictionary
        """
        area = {}
        for sector in sectors_data:
            area.update(sector)
        return area


    # def get_id_of_attack(self, coords, t_of_arrival, attacker_id):
    #     """
    #     Finds an ID of recently sent attack, returns int.
    #     1. Requests rally point screen, which contains list of all
    #     attacks & returns.
    #     2. Finds all <tr>..</tr> elements containing attacks data.
    #     3. Finds attacks that match given coordinates. At this point,
    #     we're still not sure where is a most recently sent attack
    #     (we can have returns from the same coordinates +
    #     multiple attacks in progress)
    #     4. Restores time of arrival from a given attack
    #     data and compares this time with passed t_of_arrival.
    #     The trick is, that most of arrivals in rally point
    #     screen are stamped relatively from "now" and look like
    #     "tomorrows at HH:MM:SS or today at ...", so we just try to find
    #     the closest match to passed t_of_arrival
    #     """
    #     def get_exact_match(possible_matches, t_of_arrival):
    #         t_of_arrival = int(t_of_arrival)
    #         struct_arrival = time.localtime(t_of_arrival)
    #         arrival_y_m_day = ""
    #         for i in range(3):
    #             arrival_y_m_day += str(struct_arrival[i])
    #             arrival_y_m_day += " "
    #         for attack_id, t in possible_matches:
    #             full_t = arrival_y_m_day + t
    #             restored_t = time.strptime(full_t, "%Y %m %d %H:%M:%S")
    #             restored_t = int(time.mktime(restored_t))
    #             if restored_t in range(t_of_arrival - 5, t_of_arrival + 5):
    #                 return attack_id
    #
    #     rally_screen = self.get_rally_overview(attacker_id)
    #     # attack data example: <tr>...<span id="labelText[64035559]">
    #     # Return from ...(199|293)...<td>today at 11:29:31:...</tr>
    #     attacks_ptrn = re.compile(r"<tr>[\W\w]+?labelText\W\d+[\W\w]+?</tr>")
    #     all_attacks = re.findall(attacks_ptrn, rally_screen)
    #     str_match = r"labelText\W(\d+)[\W\w]+?{x}\|{y}[\W\w]+?" \
    #                 r"at\s(\d\d:\d\d:\d\d)".format(x=coords[0],y=coords[1])
    #     match_ptrn = re.compile(str_match)
    #     possible_matches = []
    #     for attack in all_attacks:
    #         match = re.search(match_ptrn, attack)
    #         if match: possible_matches.append((match.group(1), match.group(2)))
    #     print(possible_matches)
    #     id_of_attack = get_exact_match(possible_matches, t_of_arrival)
    #     return id_of_attack
    #
    # def post_id_number(self, id_of_attack):
    #     forum_id = self.submit_id_numbers["forum_id"]
    #     thread_id = self.submit_id_numbers["thread_id"]
    #     frequency = self.submit_id_numbers["frequency"]
    #     random_delay = self.submit_id_numbers["delay"]
    #     message_data = [("do", "send"), ("message", id_of_attack)]
    #     message_data = urlencode(message_data).encode()
    #     self.lock.acquire()
    #     self.request_manager.get_tribal_forum_page()
    #     self.request_manager.get_forum_screen(forum_id)
    #     time.sleep(random.random() * 2)
    #     self.request_manager.get_last_thread_page(forum_id, thread_id)
    #     time.sleep(random.random() * 3)
    #     answer_page = self.request_manager.get_answer_page(forum_id, thread_id)
    #     csrf_token = self.get_csrf_token(answer_page)
    #     t_of_post = self.request_manager.post_message_to_forum(forum_id,
    #                                                            thread_id,
    #                                                            csrf_token,
    #                                                            message_data)
    #     if t_of_post:
    #         t_of_post = self.convert_t_to_seconds(t_of_post)
    #         self.t_of_next_post = t_of_post + frequency + random.random() * random_delay