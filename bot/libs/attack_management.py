import time
import shelve
import logging
from urllib.parse import urlencode


class AttackManager:
    """

    Uses AttackQueue class to get sequence of possible attack targets.
    Uses DecisionMaker to get attack target & amount of troops needed
    to send an attack.
    Uses RequestManager to send attack.
    Uses AttackObserver class to keep track of attacks that were sent
    (i.e. time points when new reports should be read and when some troops
    were returned back to Player's villages

    """

    def __init__(self, observer_file):
        self.attack_observer = AttackObserver(data_file=observer_file)
        self.attack_queue = AttackQueue()
        self.decision_maker = DecisionMaker()

    def build_attack_queue(self, target_villages, farm_frequency):
        targets_pending_arrival = self.attack_observer.arrival_queue
        self.attack_queue.build_queue(targets_pending_arrival, target_villages,
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

    def _get_arrival_return_t(self, t_of_attack, t_on_road):
        t_of_attack = self._convert_t_to_seconds(t_of_attack)
        t_of_arrival, t_of_return = t_of_attack + t_on_road, \
                                    t_of_attack + t_on_road * 2
        return t_of_arrival, t_of_return

    @staticmethod
    def _convert_t_to_seconds(t):
        """
        Converts str time from response.headers('Date') to seconds
        """
        # Sun, 10 Nov 2013 07:30:32 GMT
        t = t.rstrip(' GMT')
        t = time.strptime(t, '%a, %d %b %Y %H:%M:%S')
        t = time.mktime(t)
        return t


class AttackQueue:
    """
    Keeps queue of villages basing on distance to them
    and on remaining/estimated amount of resources to loot.
    Updates villages with new AttackReports.
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
                elif village.last_visited:
                    if self._is_ready_for_farm(village):
                        queue[coords] = village
                    else:
                        # has record about last visit, but there no loot or it
                        # has not finished to rest. We can enter to this condition
                        # if Village is untrusted, but it is still a visited
                        # Village, and it will not be placed to .attack_queue.
                        self.visited_villages[coords] = village

        self.queue = queue

    def _is_ready_for_farm(self, village):
        if not village.coords in self.untrusted_villages:
            if village.finished_rest(self.rest) or \
                    village.has_valuable_loot(self.rest):
                return True

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
        attack queue again (flush_visited_villages)
        """
        for attack_report in new_reports:
            coords = attack_report.coords
            if coords in self.villages:
                village = self.villages[coords]
                if not village.last_visited or \
                                village.last_visited < attack_report.t_of_attack:
                    logging.info("Villa before update: "
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

        self.flush_visited_villages()

    def flush_visited_villages(self):
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
        troops, if so - returns dict {"troops_amount": int, "t_on_road": int,
        "coords": (int, int)}, otherwise - None.
        """
        t_limit *= 3600  # to hours
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
        Evaluates if there enough troops to loot all
        village resources at the time of arrival with current troops.
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
                self._evaluate_bot_sanity(unit.name, units_needed, attack_target)
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

    @staticmethod
    def _evaluate_bot_sanity(unit_name, count, villa):
        """
        Wrote this to catch bug with 1-6 LC attacks
        and Moon-phase zillion LC attack
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
            logging.warning("Suspect Attack was sent "
                            "to {coords} with troops "
                            "{troops})".format(coords=villa.coords,
                                               troops=(unit_name, count)))


class AttackObserver:
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

    def __init__(self, data_file):
        self.data_file = data_file
        self.arrival_queue = {}
        self.return_queue = {}
        self._get_saved_attacks()

    def is_someone_arrived(self):
        time_gmt = time.mktime(time.gmtime())
        arrived = {coords: t for
                   coords, t in
                   self.arrival_queue.items() if
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
        f = shelve.open(self.data_file)
        f['arrival_queue'] = self.arrival_queue
        f['return_queue'] = self.return_queue
        f.close()

    def _get_saved_attacks(self):
        f = shelve.open(self.data_file)
        if 'arrival_queue' in f:
            registered_arrivals = f['arrival_queue']

            logging.debug("Got the next registered arrivals: "
                          "{}".format(registered_arrivals))

            self.arrival_queue = registered_arrivals
        if 'return_queue' in f:
            registered_returns = f['return_queue']

            logging.debug("Got the next saved returns: "
                          "{}".format(registered_returns))

            now = time.mktime(time.gmtime())
            for attacker_id, returns_t in registered_returns.items():
                pending_returns = [t for t in returns_t if t > now]
                self.return_queue[attacker_id] = pending_returns
        f.close()


class Unit:
    """Representation of TW unit.
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