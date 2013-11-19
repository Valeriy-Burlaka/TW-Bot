__author__ = 'Troll'

import time
import re
import random
import sys
import traceback
import shelve
from urllib.parse import urlencode
from threading import Thread
from village_management import Unit


class AttackManager(Thread):
    """
    Composite class for emulating user actions during 'farm':
    Uses VillageStateManager class to update amount of troops.
    Uses AttackQueue class to get next attack target.
    Uses AttackObserver class to keep track of attacks sent.
    Uses ReportBuilder class to update AttackQueue state.

    To send an attack, we need to perform the next actions:
    1. Request rally point page from Game.
    2. Fill input fields with needed troop values & submit them: this opens
    attack confirmation screen (We need to extract hidden 'ch' token & action_id
    from html_response data).
    3. Confirm attack. Upon confirmation, Game automatically requests rally point
    overview 1 more time.

    All calls to self.request_manager are made with acquiring Bot.Lock() to
    avoid simultaneous requests to Game server (and potential ban).
    """

    def __init__(self, request_manager, lock, village_manager, report_builder, map, observer_file, **kwargs):
        Thread.__init__(self)
        self.request_manager = request_manager  # Shared instance of RequestManager class
        self.village_manager = village_manager  # Shared instance of VillageManager class
        self.report_builder = report_builder    # Shared instance of ReportBuilder class
        self.lock = lock    # Shared instance of Bot's Lock()
        self.map = map
        self.observer_file = observer_file
        self.attackers = self.get_attackers()
        self.attack_queue = AttackQueue(self.attackers, self.map, **kwargs)
        self.new_battle_reports = 0
        self.some_troops_returned = False
        self.active = False


    def run(self):
        try:
            self.active = True
            self.attack_observer = AttackObserver(self, data_file=self.observer_file)
            # get list of coordinates where attacks were sent in previous session (and not arrived yet)
            pending_arrival = self.attack_observer.arrival_queue.keys()
            self.attack_queue.build_queue(pending_arrival)
            print("Attack queue length upon init: ", len(self.attack_queue.queue))
            self.attack_observer.start()
            print("Started to loot barbarians at: ", time.ctime())
            while self.active:
                self.cycle()
        finally:
            self.update_self_state()
            self.attack_queue.update_villages_in_map()
            self.attack_observer.save_registered_attacks()
            print("Finished to loot barbarians at: ", time.ctime())
            return

    def cycle(self):
        try:
            self.update_self_state()
            next_attacker = self.village_manager.get_next_attacking_village()   # (_id, troops_count)
            if next_attacker:
                attacker_id = next_attacker[0]
                attack_target = self.attack_queue.get_next_attack_target(next_attacker)
                if attack_target:   # [{unit_name: count, ..}, t_on_road, (x, y)]
                    troops = attack_target[0]
                    t_on_road = attack_target[1]
                    coords = attack_target[2]
                    t_of_attack = self.send_attack(attacker_id, coords, troops)
                    if t_of_attack:
                        t_of_attack = self.convert_t_to_seconds(t_of_attack)
                        troops_sent = troops
                        self.update_troops_count(attacker_id, troops_sent)
                        t_of_arrival, t_of_return = self.calc_arrival_return(t_of_attack, t_on_road)
                        self.attack_observer.register_attack(attacker_id, coords, t_of_arrival, t_of_return)
                        print("Attack sent at {time} from {source} to {coords}. Troops: {troops}".format(time=time.ctime(t_of_attack),
                                                                                                        source=attacker_id,
                                                                                                        coords=coords, troops=troops))
                else: # given player village was not able to send attack
                    print("Disabling player's village:", attacker_id)
                    self.village_manager.disable_farming_village(attacker_id)

                time.sleep(random.random() * 12) # User looks for the next village and thinks about how much troops to send
            else:
                print("Any of player's villages cannot attack, zzz...")
                time.sleep(random.random() * 30)    # User waits a bit, probably something will change
        except AttributeError:
            info = traceback.format_exception(*sys.exc_info())
            with open('errors_log.txt', 'a') as f:
                f.write("Time: {time}; Error information: {info}\n".format(time=time.ctime(), info=info))
        except TypeError:
            info = traceback.format_exception(*sys.exc_info())
            with open('errors_log.txt', 'a') as f:
                f.write("Time: {time}; Error information: {info}\n".format(time=time.ctime(), info=info))
        except BufferError:
            info = traceback.format_exception(*sys.exc_info())
            with open('errors_log.txt', 'a') as f:
                f.write("Time: {time}; Error information: {info}\n".format(time=time.ctime(), info=info))
        except Exception as e:
            info = traceback.format_exception(*sys.exc_info())
            with open('errors_log.txt', 'a') as f:
                f.write("Unexpected exception: Time: {time}; Error information: {info}\n".format(time=time.ctime(), info=info))
            print(e)

    def get_attackers(self):
        attackers = []
        for villa in self.village_manager.farming_villages.values():
            attacker_data = (villa.id, villa.coords, villa.radius)
            attackers.append(attacker_data)

        return attackers

    def send_attack(self, attacker_id, coords, troops):
        self.get_rally_overview(attacker_id)
        confirm_data = self.get_confirmation_data(attacker_id, coords, troops)
        confirm_response = self.post_confirmation(attacker_id, confirm_data)
        ch_token = self.get_ch_token(confirm_response)
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
        csrf_match = re.search(r'csrf":"(\w+)"', html_data)
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
            #print("New reports received, updating...")
            new_reports = self.report_builder.get_new_reports(reports_count)
            self.attack_queue.update_villages(new_reports)
        if self.some_troops_returned:
            return_ids = self.some_troops_returned
            print("There are returns to the next player's villages: ", return_ids)
            self.some_troops_returned = False
            self.village_manager.refresh_village_troops(return_ids)

    def update_troops_count(self, attacker_id, troops_sent):
        self.village_manager.update_troops_count(attacker_id, troops_sent)

    def calc_arrival_return(self, t_of_attack, t_on_road):
        return (t_of_attack + t_on_road, t_of_attack + t_on_road*2)

    def convert_t_to_seconds(self, t):
        """
        Converts str time from response.headers('Date') to seconds
        """
        # Sun, 10 Nov 2013 07:30:32 GMT
        t = t.rstrip(' GMT')
        t = time.strptime(t, '%a, %d %b %Y %H:%M:%S')    # returns struct_t
        t = time.mktime(t)
        return t


class AttackQueue:
    """
    Keeps queue of villages basing on distance to them
    and on remaining/estimated amount of resources to loot.
    Answers which village can be attacked next
    with current amount of troops.
    Updates villages with new AttackReports.
    Updates Map with villages.
    """

    def __init__(self, attackers, map, farm_frequency=3, capacity_threshold=2400, insert_spy_in_attack=True):
        self.attackers = attackers
        self.map = map
        self.targets_by_id = self.get_targets_in_radius()
        self.rest = farm_frequency*3600 # How long villages rest between attacks in seconds
        self.threshold = capacity_threshold # Do not send very few troops in attack
        self.units = Unit.build_units()
        self.insert_spy = insert_spy_in_attack
        self.villages = self.map.villages
        self.visited_villages = {}

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
        print("AQ, targets by id: ", targets_by_id)
        for attacker_id, targets in targets_by_id.items():
            print("Attacker {id} has {count} villages in its farm radius".format(id=attacker_id, count=len(targets)))
        return targets_by_id

    def build_queue(self, pending_arrival=None):
        """
        Builds queue from villages that are ready for farm.
        Filters out villages, where troops were already sent and have not arrived yet.
        """
        print('pending arrival in queue:', pending_arrival)
        queue = {villa.coords: villa for villa in self.villages.values() if self.is_ready_for_farm(villa)}
        if pending_arrival:
            queue = {coords: villa for coords, villa in queue.items() if coords not in pending_arrival}
        self.queue = queue


    def is_ready_for_farm(self, village):
        return village.passes_threshold(self.threshold) or village.is_fresh_meat() or village.finished_rest(self.rest)

    def get_next_attack_target(self, attacker):
        """Decides if a given attacker (PlayerVillage) can attack any target
        in it's farm radius with it's current amount of troops.
        Tries to find nearest attack target that is currently in self.queue.
        If it's possible to attack, returns list [amount of troops, time_on_road, coordinates],
        otherwise - None
        """
        if self.queue:
            print("Considering attacker: ", attacker)
            attacker_id = attacker[0]
            for attack_target in self.targets_by_id[attacker_id]:
                target_coords = attack_target[0]
                if target_coords in self.queue:
                    target_villa = self.queue[target_coords]
                    dst_to_target = attack_target[1]
                    attacker_troops = attacker[1]
                    check = self.is_attack_possible(target_villa, dst_to_target, attacker_troops)
                    if check:   # list [{troops_to_send}, t_on_road]
                        print("Attacker passed check, attack will be sent to", target_coords)
                        self.queue.pop(target_coords)
                        check.append(target_coords)
                        return check
            return
        else:
            print("Queue is empty:( Viva la new queue!")
            self.build_queue()
        return

    def is_attack_possible(self, villa, dst_from_attacker, troops_count):
        """Evaluates if there enough troops to loot all
        village resources at the time of arrival with current troops.
        Returns units needed for attack and time needed to arrive.
        """
        troops_map = self.get_troops_map(troops_count)
        for unit, count in troops_map:    # (Unit: count)
            time_on_road = self.get_time_on_the_road(dst_from_attacker, unit.speed)
            if villa.is_fresh_meat():   # No info about last_visited & remaining_capacity
                estimated_capacity = self.estimate_initial_capacity(villa)
                units_needed = self.estimate_troops_needed(unit, estimated_capacity)
            else:
                t_of_arrival = self.estimate_arrival(time_on_road)
                estimated_capacity = villa.estimate_capacity(t_of_arrival)
                units_needed = self.estimate_troops_needed(unit, estimated_capacity)
            if units_needed <= count:
                self.evaluate_bot_sanity(unit.name, units_needed, villa)
                troops_to_send = {unit.name: units_needed}
                if self.insert_spy:
                    if 'spy' in troops_count and troops_count['spy'] >= 2:
                        troops_to_send['spy'] = 2
                return [troops_to_send, time_on_road]

        else: return

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

    def estimate_initial_capacity(self, villa):
        """
        Roughly estimates village capacity basing on its .population
        """
        pop = villa.population
        if pop in range(1, 100):
            return 1200
        elif pop in range(100, 200):
            return 2400
        elif pop in range(200, 300):
            return 3200
        elif pop in range(300, 400):
            return 4800
        elif pop in range(400, 600):
            return 6400
        else:
            return 8000

    def estimate_troops_needed(self, unit, estimated_capacity):
        return round(estimated_capacity/unit.haul)

    def estimate_arrival(self, t_on_road):
        """Returns time of arrival (GMT) basing on
        given distance and speed. Speed is a unit.speed value
        and means minutes-per-tile value
        """
        time_gmt = time.mktime(time.gmtime())
        estimated_arrival = round(time_gmt + t_on_road)
        return estimated_arrival

    def get_time_on_the_road(self, distance, speed):
        return distance*speed*60    # e.g.: 6 tiles * 10 minutes-per-tile * seconds

    def update_villages(self, new_reports):
        """
        Updates self.villages with a new reports.
        Puts updated villages in self.visited_villages.
        Checks if some of visited villages can be placed in
        attack queue again (flush_visited_villages)
        """
        for coords, report in new_reports.items():
            if coords in self.villages:
                print("Villa before update: {}".format(self.villages[coords]))
                self.villages[coords].update_stats(report)
                print('Villa after update: {}'.format(self.villages[coords]))
                # Avoid adding duplicate villages to visited due to user-sent attacks, etc.
                if coords not in self.visited_villages:
                    self.visited_villages[coords] = self.villages[coords]

        self.flush_visited_villages()

    def flush_visited_villages(self):
        """
        Updates self.queue with villages that could be farmed again.
        """
        ready_for_farm = {coords: villa for coords, villa in self.visited_villages.items() if self.is_ready_for_farm(villa)}
        if ready_for_farm:
            print("Time: {}, going to flush the next villages: {}".format(time.ctime(), ready_for_farm))
            print('Queue length before flushing: {}'.format(len(self.queue)))
            for coords in ready_for_farm:
                self.queue[coords] = ready_for_farm[coords]
                self.visited_villages.pop(coords)

            print('Queue length after flushing: {}'.format(len(self.queue)))

    def update_villages_in_map(self):
        #print("Going to update next villages in map: ", self.villages)
        self.map.update_villages(self.villages)
        self.map.update_villages(self.visited_villages)

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
            print("WARNING!!! It seems that Bot is in addict!")
            print("Check attack sent to {coords} (troops sent: {troops})".format(coords=villa.coords,
                troops=(unit_name, count)))
            if villa.last_visited:
                last_visited = time.ctime(villa.last_visited)
            else: last_visited = None
            with open('SUSPECT_ATTACKS.txt', 'a') as f:
                village_info = """Attack target: coords: {coords}, remaining capacity: {remaining} \n
                                  H-rates: {rates}, Last visited: {visited}, population: {pop} \n
                                  Fresh?: {fresh}, Rested?: {rested}, Passes thresh?: {pass_thresh}\n
                                """.format(coords=villa.coords, remaining=villa.remaining_capacity,
                    rates=villa.h_rates, visited=last_visited, pop=villa.population,
                    fresh=villa.is_fresh_meat(), rested=villa.finished_rest(self.rest),
                    pass_thresh=villa.passes_threshold(self.threshold))
                f.write("Suspect attack registered at: {time}".format(time=time.ctime()))
                f.write("Attack was sent to {coords} with troops {troops})".format(coords=villa.coords,
                    troops=(unit_name, count)))
                f.write(village_info)


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
            print('Got the next registered arrivals:', registered_arrivals)
            now = time.mktime(time.gmtime())
            arrived = {coords: t for coords, t in registered_arrivals.items() if t < now}
            if arrived:
                self.manager.new_battle_reports = len(arrived)
            self.arrival_queue = {coords: t for coords, t in registered_arrivals.items() if t > now}
        if 'return_queue' in f:
            registered_returns = f['return_queue']
            print('Got the next saved returns:', registered_returns)
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



