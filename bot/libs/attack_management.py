import time
import re
import logging
from urllib.parse import urlencode

from bot.libs.common_tools import Storage


__all__ = ['AttackManager', 'DecisionMaker', 'AttackObserver', 'AttackHelper',
           'AttackQueue', 'Unit']


class AttackManager:
    """
    Responsible for providing access to retrieve & update
    operations on attack targets.
    Collaborates with AttackObserver, AttackQueue &
    DecisionMaker classes.
    """

    def __init__(self, storage_type, storage_name):
        self.attack_observer = AttackObserver(storage_type, storage_name)
        self.attack_queue = AttackQueue()
        self.decision_maker = DecisionMaker()

    def build_attack_queue(self, target_villages, farm_frequency):
        self.attack_observer.restore_saved_attacks()
        pending_arrival = self.attack_observer.get_targets_pending_arrival()
        self.attack_queue.build_queue(pending_arrival, target_villages,
                                      farm_frequency)

    def update_attack_targets(self, new_reports):
        self.attack_queue.update_villages(new_reports)

    def get_next_attack_target(self, next_attacker, t_limit_to_leave, insert_spy):
        available_targets = self.attack_queue.get_available_targets(next_attacker)
        if available_targets:
            attacker_troops = next_attacker.get_troops_count()
            next_target = self.decision_maker.get_next_attack_target(available_targets,
                                                                     attacker_troops,
                                                                     t_limit_to_leave,
                                                                     insert_spy)
            return next_target

    def get_new_arrivals(self):
        new_arrivals = self.attack_observer.is_someone_arrived()
        return new_arrivals

    def get_new_returns(self):
        new_returns = self.attack_observer.is_someone_returned()
        return new_returns

    def register_attack(self, attacker_id, target_coords,
                        t_of_attack, t_on_the_road):
        t_of_arrival, t_of_return = self._get_arrival_return_t(t_of_attack,
                                                               t_on_the_road)
        self.attack_observer.register_attack(attacker_id, target_coords,
                                             t_of_arrival, t_of_return)
        self.attack_queue.remove_villa_from_queue(target_coords)

    def save_registered_attacks(self):
        self.attack_observer.save_registered_attacks()

    def get_recent_targets_info(self):
        return self.attack_queue.villages

    def _get_arrival_return_t(self, t_of_attack, t_on_road):
        t_of_attack = self._convert_t_to_seconds(t_of_attack)
        t_of_arrival = t_of_attack + t_on_road
        t_of_return = t_of_attack + t_on_road * 2
        return t_of_arrival, t_of_return

    @staticmethod
    def _convert_t_to_seconds(t):
        """
        Converts str time from response.headers('Date') to seconds
        """
        # Sun, 10 Nov 2013 07:30:32 GMT
        t = time.strptime(t, '%a, %d %b %Y %H:%M:%S %Z')
        t = time.mktime(t)
        return t


class AttackQueue:
    """
    Provides a .queue of attack targets that helps to keep track of
    attack targets amongst all player villages.
    Provides methods to work with .queue:
    1) get available attack targets from queue
    2) remove attack target from queue
    3) update attack targets in queue with new AttackReports
    """

    def __init__(self):
        self.villages = {}
        self.rest = None
        self.queue = {}
        self.visited_villages = {}
        self.untrusted_villages = {}

    def build_queue(self, pending_arrival, target_villages, farm_frequency):
        """
        Builds queue from villages that are ready for farm.
        Filters out villages, where troops were already
        sent and have not arrived yet.
        """
        logging.debug("Targets Pending arrival: {}".format(pending_arrival))

        self.rest = farm_frequency
        self.villages = target_villages
        queue = {}
        for coords, village in target_villages.items():
            if coords not in pending_arrival and coords not in self.visited_villages:
                if not village.last_visited:
                    queue[coords] = village
                elif village.last_visited and self._is_ready_for_farm(village):
                    queue[coords] = village
                else:
                    # has record about last visit, but there no loot or it
                    # has not finished to rest. We can enter to this condition
                    # if Village is untrusted, but it is still a visited
                    # Village, and it will not be placed to .attack_queue.
                    self.visited_villages[coords] = village

        self.queue = queue

    def get_available_targets(self, attacker):
        attack_targets = attacker.attack_targets
        available_targets = ((self.queue[coords], dst) for
                             coords, dst in attack_targets if
                             coords in self.queue)
        return available_targets

    def remove_villa_from_queue(self, coords):
        self.queue.pop(coords)

    def update_villages(self, new_reports):
        """
        Updates self.villages with a new reports.
        Puts updated villages in self.visited_villages.
        Checks if some of visited villages can be placed in
        attack queue again.
        """
        for attack_report in new_reports:
            coords = attack_report.coords
            if coords in self.villages:
                village = self.villages[coords]
                # avoid update by old reports (if there was batch update)
                if not village.last_visited or \
                        village.last_visited < attack_report.t_of_attack:

                    logging.debug("Villa before update: "
                                  "{}".format(self.villages[coords]))

                    village.update_stats(attack_report)
                    self.villages[coords] = village

                    logging.info("Villa after update: "
                                 "{}".format(self.villages[coords]))

                    if attack_report.defended:
                        self.untrusted_villages[coords] = village
                    # Avoid adding duplicate villages to visited
                    # due to user-sent attacks, etc.
                    if coords not in self.visited_villages:
                        self.visited_villages[coords] = village

        self._flush_visited_villages()

    def _is_ready_for_farm(self, village):
        if not village.coords in self.untrusted_villages:
            if village.finished_rest(self.rest) or \
                    village.has_valuable_loot(self.rest):
                return True
        return False

    def _flush_visited_villages(self):
        """
        Updates self.queue with villages that could be farmed again.
        """
        ready_for_farm = {coords: villa for coords, villa in
                          self.visited_villages.items() if
                          self._is_ready_for_farm(villa)}
        if ready_for_farm:
            logging.info("Going to flush the next villages: "
                         "{}".format(ready_for_farm))
            logging.info("Queue length before flushing: "
                         "{}".format(len(self.queue)))

            for coords, village in ready_for_farm.items():
                self.queue[coords] = village
                self.visited_villages.pop(coords)

            logging.info("Queue length after flushing: "
                         "{}".format(len(self.queue)))


class DecisionMaker:
    """
    Responsible for making decision about next attack to send:
    1. Takes a list of available villages & attacker obj (PlayerVillage)
    2. Consider villages from nearest to outermost. Basing on information
    about village (distance, expected capacity) tries to form an attacking
    group from a given troops count.
    """

    def __init__(self):
        self.units = Unit.build_units()

    def get_next_attack_target(self, available_targets, attacker_troops,
                               t_limit, insert_spy):
        """
        Decides if it is possible to attack any target with current amount of
        troops, if so - returns list [{"unit_to_send": int, ...},  t_on_road,,
        target_coords], otherwise - None.
        """
        t_limit *= 3600  # to seconds
        for target in available_targets:
            attack_target = target[0]
            dst_from_attacker = target[1]
            check = self._is_attack_possible(attack_target, dst_from_attacker,
                                             t_limit, attacker_troops, insert_spy)
            if check:
                target_coords = attack_target.coords
                logging.info("Attacker passed check, attack will be sent to "
                             "{}".format(target_coords))
                check.append(target_coords)
                return check

    def _is_attack_possible(self, attack_target, distance, t_limit,
                            troops_count, insert_spy_in_attack):
        """
        Evaluates if there are enough troops to loot all village
        resources at the time of arrival with given troops count.
        Returns units needed for attack and time needed to arrive.
        """
        troops_map = self._get_troops_map(troops_count)
        for unit, count in troops_map:    # (Unit: count)
            time_on_road = self._get_time_on_the_road(distance, unit.speed)
            if time_on_road > t_limit:
                continue
            t_of_arrival = self._estimate_arrival(time_on_road)
            estimated_capacity = attack_target.estimate_capacity(t_of_arrival)
            units_needed = self._estimate_troops_needed(unit, estimated_capacity)
            if units_needed <= count:
                troops_to_send = {unit.name: units_needed}
                if insert_spy_in_attack:
                    if 'spy' in troops_count and troops_count['spy'] >= 1:
                        troops_to_send['spy'] = 1
                return [troops_to_send, time_on_road]

    def _get_troops_map(self, troops_count):
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

    @staticmethod
    def _estimate_troops_needed(unit, estimated_capacity):
        return round(estimated_capacity/unit.haul)

    @staticmethod
    def _estimate_arrival(t_on_road):
        time_gmt = time.mktime(time.gmtime())
        estimated_arrival = round(time_gmt + t_on_road)
        return estimated_arrival

    @staticmethod
    def _get_time_on_the_road(distance, speed):
        # e.g.: 6 tiles * 10 minutes-per-tile * seconds
        return distance*speed*60


class AttackObserver:
    """
    Helper class that is responsible for keeping track of
    troops arrival (in target villages) & troops return
    (in player villages).
    Provides the next interface methods:

    restore_saved_attacks:
        requests saved arrivals & returns from self.storage.
        places all saved arrivals in self.arrival_queue &
        all pending returns in sel.return_queue
    get_targets_pending_arrival:
        returns list of coordinates (x, y) which wait for
        arrival of previously sent attack.
    is_someone_arrived:
        returns number of arrived attacks & removes these
        attacks from self.arrival_queue
    is_someone_returned:
        returns id numbers of player villages, to where some troops
        have returned & cleans registered returns that are in past
    register_attack(attacker_id, coords, t_of_arrival, t_of_return):
        places t_of_return in self.return_queue (appends t_of_return
        to list of registered returns for a given attacker_id).
        places (coords): t_of_arrival in self.arrival_queue.
    save_registered_attacks:
        asks self.storage to save self.arrival_queue & .return_queue
    """

    def __init__(self, storage_type, storage_name):
        self.storage = Storage(storage_type=storage_type,
                               storage_name=storage_name)
        self.arrival_queue = {}
        self.return_queue = {}

    def restore_saved_attacks(self):
        self.arrival_queue = self.storage.get_saved_arrivals()

        logging.debug("Got the next registered arrivals: "
                      "{}".format(self.arrival_queue))

        registered_returns = self.storage.get_saved_returns()

        logging.debug("Got the next registered returns "
                      "from storage: {}".format(registered_returns))

        now = time.mktime(time.gmtime())
        for attacker_id, returns_t in registered_returns.items():
            #
            pending_returns = [t for t in returns_t if t > now]
            self.return_queue[attacker_id] = pending_returns

            logging.debug("Pending returns: ".format(registered_returns))

    def get_targets_pending_arrival(self):
        time_gmt = time.mktime(time.gmtime())
        not_arrived = [coords for coords, t in self.arrival_queue.items() if
                       t > time_gmt]
        return not_arrived

    def is_someone_arrived(self):
        time_gmt = time.mktime(time.gmtime())
        arrived = {coords: t for  coords, t in self.arrival_queue.items() if
                   t <= time_gmt}
        if arrived:
            for coords in arrived.keys():
                self.arrival_queue.pop(coords)
        return len(arrived)

    def is_someone_returned(self):
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

    def save_registered_attacks(self):
        self.storage.save_attacks(arrivals=self.arrival_queue,
                                  returns=self.return_queue)


class AttackHelper:
    """
    Contains methods that help to prepare and send attacks:

    set_confirmation_token(rally_point_html):
        takes html of rally point screen and extracts confirmation
        token from it (random alphanumeric string, generated by
        game per-session, and required to POST confirm requests).
        sets self.confirmation_token to ("token_name", "token_value')
    get_confirmation_data(rally_html, target_coords, troops_needed):
        takes attack details and composes urlencoded request data
        required to POST attack confirmation (i.e. when user
        filled desired number of troops to send in rally point
        and hits 'OK' button.
    get_attack_data(coords, troops, ch_token, action_id):
        takes attack details & unique tokens and composes urlencoded
        request data required to POST attack (i.e. when user hits 'OK'
        button second time and troops are actually sent)
    get_csrf_token(html_data):
        extracts csrf token from confirmation screen
    """

    def __init__(self):
        self.confirmation_token = None

    def set_confirmation_token(self, rally_point_html):
        """
        Extracts player token (confirmation token) from rally point html page.
        It's value is persistent and doesn't change until the session expires
        """
        # There are 2 hidden fields in rally point html.
        # The target one is a string of random alphanumeric characters
        ptrn = re.compile(r'type=\Whidden\W name=\W([\w\d]+)\W value=\W([\w\d]+)\W')
        match = re.search(ptrn, rally_point_html)
        self.confirmation_token = match.group(1), match.group(2)

    def get_confirmation_data(self, coords, troops):
        """
        Forms request data to POST confirmation.

        Data example:
        948f507c72264da32c343a=e8432083948f50&template_id=&spear=&sword=&..
        [all other troops]..&x=211&y=306&attack=Attack,
        (in order):
        confirmation token
        spear, sword = units data (empty value = '')
        x, y - target
        attack = action.

        Returns urlencoded str
        """
        request_data = []
        template = ('template_id', '')
        troops_data = self._build_troops_data(troops)
        coords = [('x', coords[0]), ('y', coords[1])]
        action = ('attack', 'Attack')

        request_data.append(self.confirmation_token)
        request_data.append(template)
        request_data.extend(troops_data)
        request_data.extend(coords)
        request_data.append(action)
        s_request_data = urlencode(request_data)

        return s_request_data.encode()

    def get_attack_data(self, coords, troops, confirmation_screen):
        """
        Forms request data to POST attack.

        Data example:
        attack=true&ch=2d27ecd3c56dcd001c086a588f2ea6c5dda3b3ac&x=211&
        y=306&action_id=275824&attack_name=&spear=0&[other troops];
        where: ch = ch_token, spear, etc. = units data (empty value = 0)

        Returns urlencoded str.
        """
        request_data = []
        attack = ('attack', 'true')
        coords = [('x', coords[0]), ('y', coords[1])]
        troops_data = self._build_troops_data(troops, empty='0')
        request_data.append(attack)
        request_data.append(self._get_ch_token(confirmation_screen))
        request_data.extend(coords)
        request_data.append(self._get_action_id(confirmation_screen))
        request_data.extend(troops_data)
        s_request_data = urlencode(request_data)

        return s_request_data.encode()

    @staticmethod
    def get_csrf_token(html_data):
        """
        Extracts csrf token from hidden field of confirmation screen HTML
        """
        csrf_match = re.search(r'csrf\W:\W([\w\d]+)\W', html_data)
        csrf = csrf_match.group(1)
        return csrf

    @staticmethod
    def _get_ch_token(html_data):
        """
        Extracts unique value (ch token) from hidden field of
        confirmation screen HTML. Returns tuple ('ch', 'ch_value')
        """
        ch_match = re.search(r'type=\Whidden\W name=\Wch\W value=\W([\w\d]+)\W',
                             html_data)
        ch_token = ('ch', ch_match.group(1))
        return ch_token

    @staticmethod
    def _get_action_id(html_data):
        """
        Extracts unique value (action_id token) from hidden field of
        confirmation screen HTML. Returns tuple ('action_id', 'value')
        """
        actionid_match = re.search(r'type=\Whidden\W name=\Waction_id\W value=\W(\d+)\W',
                                   html_data)
        action_id = ('action_id', actionid_match.group(1))
        return action_id

    @staticmethod
    def _build_troops_data(troops, empty=''):
        """
        Takes mapping of troops to send ({"unit_name": count, ...})
        Returns list of tuples [(unit_name, count), ...]
        Depending on type of request (attack or confirmation),
        zero unit count should be either empty string ('') or 0.
        """
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


class Unit:
    """
    Represents TW unit.
    """

    def __init__(self, name, attack, speed, haul):
        self.name = name
        self.attack = attack
        self.speed = speed
        self.haul = haul

    @classmethod
    def build_units(cls):
        """
        Pre-defines Unit objects for each TribalWars unit.
        """
        units = {'spear': Unit('spear', 10, 18, 25),
                 'sword': Unit('sword', 25, 22, 15),
                 'archer': Unit('archer', 15, 18, 10),
                 'axe': Unit('axe', 40, 18, 10),
                 'spy': Unit('spy', 0, 9, 0),
                 'light': Unit('light', 130, 10, 80),
                 'marcher': Unit('marcher', 120, 10, 50),
                 'heavy': Unit('heavy', 150, 11, 50)}
        return units

    @staticmethod
    def get_def_names():
        return ['spear', 'sword', 'archer', 'axe', 'spy',
                'light', 'marcher', 'heavy']

    @staticmethod
    def get_off_names():
        return ['axe', 'spy', 'light', 'marcher', 'heavy']

    def __str__(self):
        return "Unit:=>{0}, speed:=>{1}, haul:=>{2}".format(self.name,
                                                            self.speed,
                                                            self.haul)

    def __repr__(self):
        return self.__str__()