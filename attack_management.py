import time
import re
import random
import sys
import traceback
import shelve
from urllib.parse import urlencode
from threading import Thread
from village_management import Unit
from data_management import write_log_message


class AttackManager(Thread):
    """
    Composite class that emulates user's actions during 'farm' process.

    Uses VillageManager class to get attacking Player's villages and
    their amount of troops.
    Uses AttackQueue class to get sequence of possible attack targets.
    Uses DecisionMaker to get attack target & amount of troops needed
    to send an attack.
    Uses RequestManager to send attack.
    Uses AttackObserver class to keep track of attacks that were sent
    (i.e. time points when new reports should be read and when some troops
    were returned back to Player's villages)
    Uses ReportBuilder class to update AttackQueue state.

    To send an attack, we need to perform the next actions:
    1. Request rally point page from Game.
    2. "Fill" input fields with needed troop values & submit them: this opens
    attack confirmation screen (We need to extract hidden 'ch' token & action_id
    from html_response data).
    3. Confirm attack. Upon confirmation, Game automatically requests rally point
    overview 1 more time.

    All calls to self.request_manager are made with acquiring Lock() (single
    instance is shared amongst all classes that call RequestManager) to
    avoid simultaneous requests to Game server (and potential ban).
    """

    def __init__(self, request_manager, lock, village_manager, report_builder, map, observer_file,
                 logfile, events_file, submit_id_numbers, t_limit_to_leave=4, farm_frequency=3, insert_spy_in_attack=True):
        Thread.__init__(self)
        self.request_manager = request_manager  # Shared instance of RequestManager class
        self.village_manager = village_manager  # Shared instance of VillageManager class
        self.report_builder = report_builder    # Shared instance of ReportBuilder class
        self.decision_maker = DecisionMaker(events_file, t_limit_to_leave, insert_spy_in_attack)
        self.lock = lock    # Shared instance of Bot's Lock()
        self.map = map
        self.observer_file = observer_file
        self.logfile = logfile
        self.events_file = events_file
        self.attackers = self.village_manager.get_attackers()
        self.attack_queue = AttackQueue(self.attackers, self.map, self.events_file, farm_frequency)
        self.new_battle_reports = 0
        self.some_troops_returned = False
        self.active = False
        self.in_cycle = False
        self.submit_id_numbers = submit_id_numbers
        self.t_of_next_post = 0


    def run(self):
        self.active = True
        self.attack_observer = AttackObserver(self, data_file=self.observer_file)
        # get list of coordinates where attacks were sent in previous session (and not arrived yet)
        pending_arrival = self.attack_observer.arrival_queue.keys()
        self.update_self_state()
        self.attack_queue.build_queue(pending_arrival)
        write_log_message(self.events_file, "There are {} targets in attack queue".format(len(self.attack_queue.queue)))
        self.attack_observer.start()
        write_log_message(self.events_file, "Started to loot barbarians")
        while self.active:
            self.cycle()

    def stop(self):
        self.active = False
        while self.in_cycle:
            time.sleep(1)
        self.attack_observer.save_registered_attacks()
        self.update_self_state()
        self.attack_queue.update_villages_in_map()
        write_log_message(self.events_file, "Finished to loot barbarians")

    def cycle(self):
        try:
            self.in_cycle = True
            self.update_self_state()
            next_attacker = self.village_manager.get_next_attacking_village()   # (_id, troops_count)
            if next_attacker:
                attacker_id, troops_count = next_attacker[0], next_attacker[1]
                attack_target = self.prepare_next_target(attacker_id, troops_count)
                if attack_target:   # [{unit_name: count, ..}, t_on_road, (x, y)]
                    troops, t_on_road, coords = attack_target[0], attack_target[1], attack_target[2]
                    t_of_attack = self.send_attack(attacker_id, coords, troops)
                    if t_of_attack:
                        self.attack_queue.remove_villa_from_queue(coords)
                        t_of_attack = self.convert_t_to_seconds(t_of_attack)
                        self.update_troops_count(attacker_id, troops)
                        t_of_arrival, t_of_return = t_of_attack + t_on_road, t_of_attack + t_on_road * 2
                        self.attack_observer.register_attack(attacker_id, coords, t_of_arrival, t_of_return)
                        event_msg = "Attack sent at: {t1} from: {s} to: {c}. Troops: {tr}, arrival: {t2}".format(t1=time.ctime(t_of_attack),
                                                                                                                s=attacker_id, c=coords,
                                                                                                                tr=troops, t2=t_of_arrival)
                        write_log_message(self.events_file, event_msg)
                        if self.submit_id_numbers and time.mktime(time.gmtime()) > self.t_of_next_post:
                            id_of_attack = self.get_id_of_attack(coords, t_of_arrival, attacker_id)
                            if id_of_attack:
                                self.post_id_number(id_of_attack)
                                print("Posted {p_id}. See attacker {a_id}, attack on coords {c}".format(p_id=id_of_attack,a_id=attacker_id, c=coords))

                else: # given player village was not able to send attack
                    event_msg = "Disabling player's village: {id}".format(id=attacker_id)
                    write_log_message(self.events_file, event_msg)
                    self.village_manager.disable_farming_village(attacker_id)

                time.sleep(random.random() * 12) # User looks for the next village and thinks about how much troops to send
            else:
                time.sleep(random.random() * 30)    # User waits a bit, probably something will change
        except AttributeError:
            error_info = traceback.format_exception(*sys.exc_info())
            str_info = "Error information: {info}".format(info=error_info)
            write_log_message(self.logfile, str_info)
        except TypeError:
            error_info = traceback.format_exception(*sys.exc_info())
            str_info = "Error information: {info}".format(info=error_info)
            write_log_message(self.logfile, str_info)
        finally:
            self.in_cycle = False

    def prepare_next_target(self, attacker_id, troops_count):
        available_targets = self.attack_queue.get_available_targets(attacker_id)
        attack_target = self.decision_maker.get_next_attack_target(available_targets, troops_count)
        return attack_target

    def send_attack(self, attacker_id, coords, troops):
        self.get_rally_overview(attacker_id)
        confirm_data = self.get_confirmation_data(attacker_id, coords, troops)
        confirm_response = self.post_confirmation(attacker_id, confirm_data)
        # Confirmation may be unsuccessful, if there were no enough troops in village (e.g. due to user-sent attacks)
        try:
            ch_token = self.get_ch_token(confirm_response)
        except AttributeError:
            self.village_manager.refresh_village_troops(attacker_id)
            return

        action_id = self.get_action_id(confirm_response)
        csrf = self.get_csrf_token(confirm_response)
        attack_data = self.get_attack_data(coords, troops, ch_token, action_id)
        t_of_attack = self.post_attack(attacker_id, attack_data, csrf)
        return t_of_attack

    def post_confirmation(self, attacker_id, confirm_data):
        """
        Submits confirm data. Returns str HTML.
        """
        time.sleep(random.random() * 5) # User hits in fields to select troops to send
        self.lock.acquire()
        response_data = self.request_manager.post_confirmation(attacker_id, confirm_data)
        self.lock.release()
        return response_data

    def post_attack(self, attacker_id, request_data, csrf):
        time.sleep(random.random() * 2) # User just hits OK button
        self.lock.acquire()
        t_of_attack = self.request_manager.post_attack(attacker_id, request_data, csrf)
        self.lock.release()
        return t_of_attack

    def get_rally_overview(self, attacker_id):
        time.sleep(random.random() * 3)   # User hits on village and clicks "send attack"
        self.lock.acquire()
        html_data = self.request_manager.get_rally_overview(attacker_id)
        self.lock.release()
        return html_data

    def get_ch_token(self, html_data):
        """
        Extracts unique value (ch token) from hidden field of confirmation screen HTML.
        Returns tuple ('ch', 'ch_value')
        """
        ch_match = re.search(r'type="hidden" name="ch" value="([\w\d]+)"', html_data)
        ch_token = ('ch', ch_match.group(1))
        return ch_token

    def get_action_id(self, html_data):
        """
        Extracts unique value (action_id token) from hidden field of confirmation screen HTML.
        Returns tuple ('action_id', 'value')
        """
        actionid_match = re.search(r'type="hidden" name="action_id" value="(\d+)"', html_data)
        action_id = ('action_id', actionid_match.group(1))
        return action_id

    def get_csrf_token(self, html_data):
        csrf_match = re.search(r'csrf\W:\W(\w+)\W', html_data)
        csrf = csrf_match.group(1)
        return csrf

    def get_confirmation_token(self, attacker_id):
        """
        Extracts player token (confirmation token) from rally point html page
        """
        rally_html = self.get_rally_overview(attacker_id)
        ptrn = re.compile(r'type="hidden" name="([\w\d]+)" value="([\w\d]+)"')
        match = re.search(ptrn, rally_html)
        return (match.group(1), match.group(2))

    def get_attack_data(self, coords, troops, ch_token, action_id):
        """
        Forms request data to POST attack.
        Data example:
        attack=true&ch=2d27ecd3c56dcd001c086a588f2ea6c5dda3b3ac&x=211&y=306&action_id=275824&attack_name=&spear=0&[other troops],
        where ch = ch_token, spear, etc. = units data (empty value = 0)
        Returns urlencoded str.
        """
        request_data = []   # form POST data from sequence: we need to retain order for request_data
        attack = ('attack', 'true')
        coords = [('x', coords[0]), ('y', coords[1])]
        attack_name = ('attack_name', '')
        troops_data = self.build_troops_data(troops, empty='0')
        request_data.append(attack)
        request_data.append(ch_token)
        request_data.extend(coords)
        request_data.append(action_id)
        request_data.append(attack_name)
        request_data.extend(troops_data)
        s_request_data = urlencode(request_data)

        return s_request_data.encode()

    def get_confirmation_data(self, attacker_id, coords, troops):
        """
        Forms request data to POST confirmation.
        Data example:
        948f507c72264da32c343a=e8432083948f50&template_id=&spear=&sword=&..[all other troops]..&x=211&y=306&attack=Attack,
        where 1st = confirmation token
        spear, sword = units data (empty value = '')
        x, y - target
        attack = action.
        Returns urlencoded str
        """
        request_data = []   # form POST data from sequence: we need to retain order for request_data
        template = ('template_id', '')
        troops_data = self.build_troops_data(troops)
        coords = [('x', coords[0]), ('y', coords[1])]
        action = ('attack', 'Attack')

        request_data.append(self.get_confirmation_token(attacker_id))
        request_data.append(template)
        request_data.extend(troops_data)
        request_data.extend(coords)
        request_data.append(action)
        s_request_data = urlencode(request_data)

        return s_request_data.encode()

    def build_troops_data(self, troops, empty=''):
        # spear=&sword=&axe=&archer=&spy=&light=&marcher=&heavy=&ram=&catapult=&knight=&snob=&
        units_order = ('spear', 'sword', 'axe', 'archer', 'spy',
                        'light', 'marcher', 'heavy', 'ram', 'catapult',
                        'knight', 'snob',)
        troops_data = []
        for unit_name in units_order:
            if unit_name in troops:
                unit_data = (unit_name, troops[unit_name])
            else:
                unit_data = (unit_name, empty)
            troops_data.append(unit_data)
        return troops_data

    def update_self_state(self):
        if self.new_battle_reports:
            # Refresh flag  at once we entered here, because while
            # getting new reports/overview, AttackObserver may notify us again.
            reports_count = self.new_battle_reports
            self.new_battle_reports = 0
            new_reports = self.report_builder.get_new_reports(reports_count)
            self.attack_queue.update_villages(new_reports)
        if self.some_troops_returned:
            return_ids = self.some_troops_returned
            event_msg = "There are returns to the next player's villages: {ids}".format(ids=return_ids)
            write_log_message(self.events_file, event_msg)
            self.some_troops_returned = False
            for villa_id in return_ids:
                self.village_manager.refresh_village_troops(villa_id)

    def update_troops_count(self, attacker_id, troops_sent):
        self.village_manager.update_troops_count(attacker_id, troops_sent)

    def convert_t_to_seconds(self, t):
        """
        Converts str time from response.headers('Date') to seconds
        """
        # Sun, 10 Nov 2013 07:30:32 GMT
        t = t.rstrip(' GMT')
        t = time.strptime(t, '%a, %d %b %Y %H:%M:%S')    # returns struct_t
        t = time.mktime(t)
        return t

    def get_id_of_attack(self, coords, t_of_arrival, attacker_id):
        """
        Finds an ID of recently sent attack, returns int.
        1. Requests rally point screen, which contains list of all
        attacks & returns.
        2. Finds all <tr>..</tr> elements containing attacks data.
        3. Finds attacks that match given coordinates. At this point,
        we're still not sure where is a most recently sent attack
        (we can have returns from the same coordinates + multiple attacks in progress)
        4. Restores time of arrival from a given attack data and compares this time
        with passed t_of_arrival. The trick is, that most of arrivals in rally point
        screen are stamped relatively from "now" and look like "tomorrows at HH:MM:SS
        or today at ...", so we just try to find the closest match to passed t_of_arrival
        """
        def get_exact_match(possible_matches, t_of_arrival):
            t_of_arrival = int(t_of_arrival)
            struct_arrival = time.localtime(t_of_arrival)
            arrival_y_m_day = ""
            for i in range(3):
                arrival_y_m_day += str(struct_arrival[i])
                arrival_y_m_day += " "
            for attack_id, t in possible_matches:
                full_t = arrival_y_m_day + t
                restored_t = time.strptime(full_t, "%Y %m %d %H:%M:%S")
                restored_t = int(time.mktime(restored_t))
                if restored_t in range(t_of_arrival - 5, t_of_arrival + 5):
                    return attack_id

        rally_screen = self.get_rally_overview(attacker_id)
        # attack data example: <tr>...<span id="labelText[64035559]">Return from ...(199|293)...<td>today at 11:29:31:...</tr>
        attacks_ptrn = re.compile(r"<tr>[\W\w]+?labelText\W\d+[\W\w]+?</tr>")
        all_attacks = re.findall(attacks_ptrn, rally_screen)
        str_match = r"labelText\W(\d+)[\W\w]+?{x}\|{y}[\W\w]+?at\s(\d\d:\d\d:\d\d)".format(x=coords[0],y=coords[1])
        match_ptrn = re.compile(str_match)
        possible_matches = []
        for attack in all_attacks:
            match = re.search(match_ptrn, attack)
            if match: possible_matches.append((match.group(1), match.group(2)))
        print(possible_matches)
        id_of_attack = get_exact_match(possible_matches, t_of_arrival)
        return id_of_attack

    def post_id_number(self, id_of_attack):
        forum_id = self.submit_id_numbers["forum_id"]
        thread_id = self.submit_id_numbers["thread_id"]
        frequency = self.submit_id_numbers["frequency"]
        random_delay = self.submit_id_numbers["delay"]
        message_data = [("do", "send"), ("message", id_of_attack)]
        message_data = urlencode(message_data).encode()
        self.lock.acquire()
        self.request_manager.get_tribal_forum_page()
        self.request_manager.get_forum_screen(forum_id)
        time.sleep(random.random() * 2)
        self.request_manager.get_last_thread_page(forum_id, thread_id)
        time.sleep(random.random() * 3)
        answer_page = self.request_manager.get_answer_page(forum_id, thread_id)
        csrf_token = self.get_csrf_token(answer_page)
        t_of_post = self.request_manager.post_message_to_forum(forum_id, thread_id, csrf_token, message_data)
        self.lock.release()
        if t_of_post:
            t_of_post = self.convert_t_to_seconds(t_of_post)
            self.t_of_next_post = t_of_post + frequency + random.random() * random_delay




class AttackQueue:
    """
    Keeps queue of villages basing on distance to them
    and on remaining/estimated amount of resources to loot.
    Updates villages with new AttackReports.
    Updates Map with villages.
    """

    def __init__(self, attackers, map, events_file, farm_frequency):
        self.attackers = attackers
        self.map = map
        self.events_file = events_file
        self.rest = farm_frequency  # hours
        self.targets_by_id = self.get_targets_in_radius()
        self.villages = self.map.villages
        self.queue = {}
        self.visited_villages = {}
        self.untrusted_villages = {}

    def get_targets_in_radius(self):
        """
        Requests Map for a list of attack targets in a given radius.
        (Each attacks target is a tuple((x, y), distance_from_attacker)
        Returns a dict, where keys are attackers id (PlayerVillages), values -
        list of targets sorted ascending (nearest first)
        """
        targets_by_id = {}
        for attacker_data in self.attackers:    # (villa.id, villa.coords, villa.radius)
            attacker_id = attacker_data[0]
            attacker_coords = attacker_data[1]
            preferred_radius = attacker_data[2]
            targets_in_radius = self.map.get_targets_in_radius(preferred_radius, attacker_coords)
            targets_in_radius = sorted(targets_in_radius, key=lambda x: x[1])
            targets_by_id[attacker_id] = targets_in_radius
        event_msg = "AttackQueue: targets by id: {}".format(targets_by_id)
        write_log_message(self.events_file, event_msg)
        for attacker_id, targets in targets_by_id.items():
            event_msg = "Attacker {id} has {c} villages in its farm radius".format(id=attacker_id, c=len(targets))
            write_log_message(self.events_file, event_msg)
        return targets_by_id

    def build_queue(self, pending_arrival):
        """
        Builds queue from villages that are ready for farm.
        Filters out villages, where troops were already sent and have not arrived yet.
        """
        event_msg = "Targets Pending arrival: {}".format(pending_arrival)
        write_log_message(self.events_file, event_msg)
        queue = {}
        for coords, village in self.villages.items():
            if coords not in pending_arrival and coords not in self.visited_villages:
                if not village.last_visited:
                    queue[coords] = village
                elif village.last_visited:
                    if self.is_ready_for_farm(village):
                        queue[coords] = village
                    else:
                        # has record about last visit, but there no loot or it has not finished to rest.
                        # We also can enter to this condition if Village is untrusted, but it is still
                        # a visited Village, and it will not be placed to .attack_queue.
                        self.visited_villages[coords] = village

        self.queue = queue

    def is_ready_for_farm(self, village):
        if not village.coords in self.untrusted_villages:
            if village.finished_rest(self.rest):
                return True
            elif village.has_valuable_loot(self.rest):
                return True
            else:
                return False
        else:
            return False

    def get_available_targets(self, attacker_id):
        attack_targets = self.targets_by_id[attacker_id]
        available_targets = ((self.queue[coords], dst) for coords, dst in attack_targets if coords in self.queue)
        return available_targets

    def remove_villa_from_queue(self, coords):
        self.queue.pop(coords)

    def update_villages(self, new_reports):
        """
        Updates self.villages with a new reports.
        Puts updated villages in self.visited_villages.
        Checks if some of visited villages can be placed in
        attack queue again (flush_visited_villages)
        """
        for attack_report in new_reports:
            coords = attack_report.coords
            if coords in self.villages:
                village = self.villages[coords]
                if not village.last_visited or village.last_visited < attack_report.t_of_attack:
                    event_msg = "Villa before update: {}".format(self.villages[coords])
                    write_log_message(self.events_file, event_msg)
                    village.update_stats(attack_report)
                    self.villages[coords] = village
                    event_msg = "Villa after update: {}".format(self.villages[coords])
                    write_log_message(self.events_file, event_msg)
                    if attack_report.defended:
                        self.untrusted_villages[coords] = village
                    # Avoid adding duplicate villages to visited due to user-sent attacks, etc.
                    if coords not in self.visited_villages:
                        self.visited_villages[coords] = village

        self.flush_visited_villages()

    def flush_visited_villages(self):
        """
        Updates self.queue with villages that could be farmed again.
        """
        ready_for_farm = {coords: villa for coords, villa in self.visited_villages.items() if self.is_ready_for_farm(villa)}
        if ready_for_farm:
            event_msg = "Going to flush the next villages: {}".format(ready_for_farm)
            write_log_message(self.events_file, event_msg)
            event_msg = "Queue length before flushing: {}".format(len(self.queue))
            write_log_message(self.events_file, event_msg)
            for coords, village in ready_for_farm.items():
                self.queue[coords] = village
                self.visited_villages.pop(coords)

            event_msg = "Queue length after flushing: {}".format(len(self.queue))
            write_log_message(self.events_file, event_msg)

    def update_villages_in_map(self):
        self.map.update_villages(self.villages)
        self.map.update_villages(self.visited_villages)


class DecisionMaker:
    """
    Responsible for making decision about next attack to send:
    1. Takes a list of available villages & attacker's current troops
    2. Consider villages from nearest to outermost. Basing on information
    about village (distance, expected capacity) tries to form an attacking
    group from a given troops count.
    """

    def __init__(self, events_file, t_limit_to_leave, insert_spy_in_attack):
        self.events_file = events_file
        # T limit to leave PlayerVillage for units (in seconds). Prevents sending slow units in a far galaxy.
        self.t_limit = t_limit_to_leave * 3600
        self.units = Unit.build_units()
        self.insert_spy = insert_spy_in_attack

    def get_next_attack_target(self, targets, attacker_troops):
        """Decides if it is possible to attack any target with a given amount
        of troops, if so - returns list [amount of troops, time_on_road, coordinates],
        otherwise - None.
        """
        for target in targets:
            target_villa = target[0]
            dst_from_attacker = target[1]
            check = self.is_attack_possible(target_villa, dst_from_attacker, attacker_troops)
            if check:   # list [{troops_to_send}, t_on_road]
                target_coords = target_villa.coords
                event_msg = "Attacker passed check, attack will be sent to {}".format(target_coords)
                write_log_message(self.events_file, event_msg)
                check.append(target_coords)
                return check

    def is_attack_possible(self, villa, distance, troops_count):
        """Evaluates if there enough troops to loot all
        village resources at the time of arrival with current troops.
        Returns units needed for attack and time needed to arrive.
        """
        troops_map = self.get_troops_map(troops_count)
        for unit, count in troops_map:    # (Unit: count)
            time_on_road = self.get_time_on_the_road(distance, unit.speed)
            if time_on_road > self.t_limit:
                continue
            t_of_arrival = self.estimate_arrival(time_on_road)
            estimated_capacity = villa.estimate_capacity(t_of_arrival)
            units_needed = self.estimate_troops_needed(unit, estimated_capacity)
            if units_needed <= count:
                self.evaluate_bot_sanity(unit.name, units_needed, villa)
                troops_to_send = {unit.name: units_needed}
                if self.insert_spy:
                    if 'spy' in troops_count and troops_count['spy'] >= 1:
                        troops_to_send['spy'] = 1
                return [troops_to_send, time_on_road]

    def get_troops_map(self, troops_count):
        troops_map = []
        for unit_name, count in troops_count.items():
            if unit_name == 'spy':
                continue
            unit = self.units[unit_name]
            unit_data = (unit, count)
            troops_map.append(unit_data)
        # sort from slow to fast (Unit.speed is a minutes-per-tile)
        troops_map = sorted(troops_map, key=lambda x: x[0].speed, reverse=True)
        return troops_map

    def estimate_troops_needed(self, unit, estimated_capacity):
        return round(estimated_capacity/unit.haul)

    def estimate_arrival(self, t_on_road):
        time_gmt = time.mktime(time.gmtime())
        estimated_arrival = round(time_gmt + t_on_road)
        return estimated_arrival

    def get_time_on_the_road(self, distance, speed):
        return distance*speed*60    # e.g.: 6 tiles * 10 minutes-per-tile * seconds


    def evaluate_bot_sanity(self, unit_name, count, villa):
        """
        Wrote this to catch bug with 1-6 LC attacks and Moon-phase zillion LC attack
        """
        bot_sane = True
        if unit_name == 'axe':
            if count <= 50 or count >= 2000: bot_sane = False
        elif unit_name == 'light':
            if count <= 6 or count >= 300: bot_sane = False
        elif unit_name == 'marcher':
            if count <= 10 or count >= 480: bot_sane = False
        elif unit_name == 'heavy':
            if count <= 10 or count >= 480: bot_sane = False

        if not bot_sane:
            write_log_message(self.events_file, "Suspect Attack was sent to {coords} with troops {troops})".format(coords=villa.coords,                                                                                                            troops=(unit_name, count)))
            write_log_message(self.events_file, str(villa))
            print("WARNING: Suspect attack registered! See log message for details.")


class Observer(Thread):

    def __init__(self, parent_manager):
        Thread.__init__(self)
        self.manager = parent_manager


class AttackObserver(Observer):
    """
    Notifies 'parent' manager(Attack) about 2 events:
    1. Troops, that were sent, arrived in target village (need to update
     reports)
    2. Troops sent returned back (update troops map,
    possibly can send new attack).

    When stopped, saves registered arrivals/returns (that were not
    flushed yet) in local file. When inited again, checks local file
    for saved registrations: 1. If any arrivals/returns are in future,
    they are placed back in queues. If any arrivals are in past, possibly
    there are new reports.
    """

    def __init__(self, attack_manager, data_file='attack_observer'):
        Observer.__init__(self, attack_manager)
        self.data_file = data_file
        self.arrival_queue = {}
        self.return_queue = {}
        self.get_saved_attacks()

    def run(self):
        # to do: read about threading Events
        try:
            while self.manager.active:
                new_reports = self.someone_arrived()
                if new_reports:
                        self.manager.new_battle_reports += new_reports
                new_return_ids = self.someone_returned()
                if new_return_ids:
                    self.manager.some_troops_returned = new_return_ids
                time.sleep(1)
        finally:
            self.save_registered_attacks()
        return

    def get_saved_attacks(self):
        f = shelve.open(self.data_file)
        if 'arrival_queue' in f:
            registered_arrivals = f['arrival_queue']
            event_msg = "Got the next registered arrivals: {}".format(registered_arrivals)
            write_log_message(self.manager.events_file, event_msg)
            now = time.mktime(time.gmtime())
            arrived = {coords: t for coords, t in registered_arrivals.items() if t < now}
            if arrived:
                self.manager.new_battle_reports = len(arrived)
            self.arrival_queue = {coords: t for coords, t in registered_arrivals.items() if t > now}
        if 'return_queue' in f:
            registered_returns = f['return_queue']
            event_msg = "Got the next saved returns: {}".format(registered_returns)
            write_log_message(self.manager.events_file, event_msg)
            now = time.mktime(time.gmtime())
            for attacker_id, returns_t in registered_returns.items():
                pending_returns = [t for t in returns_t if t > now]
                self.return_queue[attacker_id] = pending_returns
        f.close()

    def save_registered_attacks(self):
        f = shelve.open(self.data_file)
        f['arrival_queue'] = self.arrival_queue
        f['return_queue'] = self.return_queue
        f.close()

    def someone_arrived(self):
        time_gmt = time.mktime(time.gmtime())
        arrived = {coords: t for coords, t in self.arrival_queue.items() if t <= time_gmt}
        if arrived:
            for coords in arrived.keys():
                self.arrival_queue.pop(coords)
        return len(arrived)

    def someone_returned(self):
        time_gmt = time.mktime(time.gmtime())
        return_ids = []
        for attacker_id, returns in self.return_queue.items():
            returned = [t for t in returns if t <= time_gmt]
            if returned:
                return_ids.append(attacker_id)
                for t in returned:
                    self.return_queue[attacker_id].remove(t)

        return return_ids

    def register_attack(self, attacker_id, coords, t_of_arrival, t_of_return):
        self.arrival_queue[coords] = t_of_arrival
        if attacker_id in self.return_queue:
            self.return_queue[attacker_id].append(t_of_return)
        else:
            self.return_queue[attacker_id] = [t_of_return]



