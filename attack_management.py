__author__ = 'Troll'

import time
import re
import random
import sys
import traceback
import shelve
from urllib.parse import urlencode
from threading import Thread
from map_management import Map
from village_management import VillageStateManager



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

    def __init__(self, village_x, village_y, request_manager, report_builder, lock, **kwargs):
        Thread.__init__(self)
        self.x = village_x
        self.y = village_y
        self.request_manager = request_manager  # Shared instance of RequestManager class
        self.report_builder = report_builder    # Shared instance of ReportBuilder class
        self.lock = lock    # Shared instance of Bot's Lock()
        self.attack_queue = AttackQueue(self.x, self.y, self.request_manager, **kwargs)
        self.state_manager = VillageStateManager(self.request_manager, self.lock)
        self.troops_map = self.state_manager.get_troops_map()   # {Unit: count, ...}
        self.confirmation_token = self.get_confirmation_token() # it's not changing even between browser's sessions
        self.new_battle_reports = False
        self.some_troops_returned = False
        self.active = False

    def run(self):
        try:
            self.active = True
            self.attack_observer = AttackObserver(self)
            self.attack_observer.start()
            print("Started to loot barbarians at: ", time.ctime())
            while self.active:
                self.cycle()
        except Exception as e:
            info = traceback.format_exception(*sys.exc_info())
            with open('errors_log.txt', 'a') as f:
                f.write("Time: {time}; Error information: {info}\n".format(time=time.ctime(), info=info))
            print(e)
        finally:
            self.update_self_state()
            self.attack_queue.update_villages_in_map()
            print("Finished to loot barbarians at: ", time.ctime())
            return

    def cycle(self):
        try:
            self.update_self_state()
            troops_map = self.troops_map
            attack_target = self.attack_queue.get_next_attack_target(troops_map)
            if attack_target:   # (coords(tuple), {unit:count}, t_on_road(float)
                coords = attack_target[0]
                troops = attack_target[1]
                t_on_road = attack_target[2]
                t_of_attack = self.send_attack(coords, troops)
                if t_of_attack:
                    t_of_attack = self.convert_t_to_seconds(t_of_attack)
                    troops_sent = troops
                    self.update_troops_count(troops_sent)
                    t_of_arrival, t_of_return = self.calc_arrival_return(t_of_attack, t_on_road)
                    self.attack_observer.register_attack(t_of_arrival, t_of_return)
                    print("Attack sent at {time} to {coords}. Troops: {troops}".format(time=t_of_attack, coords=coords, troops=troops))

            time.sleep(random.random() * 6) # User looks for the next village and thinks how much troops to send
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

    def send_attack(self, coords, troops):
        self.get_rally_overview()
        confirm_data = self.get_confirmation_data(coords, troops)
        confirm_response = self.post_confirmation(confirm_data.encode())
        ch_token = self.get_ch_token(confirm_response)
        action_id = self.get_action_id(confirm_response)
        csrf = self.get_csrf_token(confirm_response)

        attack_data = self.get_attack_data(coords, troops, ch_token, action_id)
        t_of_attack = self.post_attack(attack_data.encode(), csrf)
        return t_of_attack

    def post_confirmation(self, confirm_data):
        """
        Submits confirm data. Returns str HTML.
        """
        time.sleep(random.random() * 3) # User hits in fields to select troops to send
        self.lock.acquire()
        response_data = self.request_manager.post_confirmation(confirm_data)
        self.lock.release()
        return response_data

    def post_attack(self, request_data, csrf):
        time.sleep(random.random()) # User just hits OK button
        self.lock.acquire()
        t_of_attack = self.request_manager.post_attack(request_data, csrf)
        self.lock.release()
        return t_of_attack

    def get_rally_overview(self):
        time.sleep(random.random() * 1.5)   # User hits on village and clicks "send attack"
        self.lock.acquire()
        html_data = self.request_manager.get_rally_overview()
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

    def get_action_id(selfself, html_data):
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

    def get_confirmation_token(self):
        """
        Extracts player token (confirmation token) from rally point html page
        """
        rally_html = self.get_rally_overview()
        ptrn = re.compile(r'type="hidden" name="([\w\d]+)" value="([\w\d]+)"')
        match = re.search(ptrn, rally_html)
        return (match.group(1), match.group(2))

    def get_attack_data(self, coords, troops, ch_token, action_id):
        """
        Forms request data to POST attack.
        Data example:
        attack=true&ch=2d27ecd3c56dcd001c086a588f2ea6c5dda3b3ac&x=211&y=306&action_id=275824&attack_name=&spear=0&[other troops],
        where ch = ch_token, spear, etc. = units data (empty value = 0)
        Returns urlencoded str
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

        return s_request_data

    def get_confirmation_data(self, coords, troops):
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

        request_data.append(self.confirmation_token)
        request_data.append(template)
        request_data.extend(troops_data)
        request_data.extend(coords)
        request_data.append(action)
        s_request_data = urlencode(request_data)

        return s_request_data

    def build_troops_data(self, troops, empty='', insert_spy=True):
        if insert_spy:
            troops = self.insert_spy_in_attack(troops)
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
            # Set flag to False at once we entered here, because while
            # getting new reports/overview, AttackObserver may notify us again.
            self.new_battle_reports = False
            #print("New reports received, updating...")
            new_reports = self.report_builder.get_new_reports()
            self.attack_queue.update_villages(new_reports)
        if self.some_troops_returned:
            self.some_troops_returned = False
            #print("Troops returned, updating troops...")
            #print("current troops: {}".format(self.troops_map))
            self.troops_map = self.state_manager.get_troops_map()
            #print("updated troops: {}".format(self.troops_map))

    def update_troops_count(self, troops_sent):
        for key, value in troops_sent.items():
            self.troops_map[key] -= value

    def insert_spy_in_attack(self, troops):
        if 'spy' in self.troops_map and self.troops_map['spy'] >= 2:
            troops['spy'] = 2
        return troops

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

    def __init__(self, x, y, request_manager, map_depth=2, mapfile='map', queue_depth=5,
                 farm_frequency=3, farm_radius=24, capacity_threshold=2400 ):
        self.map = Map(x, y, request_manager, depth=map_depth, mapfile=mapfile)
        self.depth = queue_depth    # Number of next priorities
        self.rest = farm_frequency*3600 # How long villages rest between attacks in seconds
        self.radius = farm_radius   # Radius from player's village in tiles
        self.threshold = capacity_threshold # Do not send very few troops in attack
        self.villages = self.map.get_villages_in_range(self.radius)
        self.queue = []
        self.visited_villages = []
        self.units = self.init_units()
        self.build_queue()

    def build_queue(self):
        """Builds queue from villages that are ready for farm
        and sorts it ascending by distance (nearest=first)"""
        # v_data = {'village': Village, 'distance':distance]
        queue = [villa for villa in self.villages.values() if self.is_ready_for_farm(villa)]
        # assign queue sorted by distance
        self.queue = sorted(queue, key=lambda x: x.dist_from_base)

    def is_ready_for_farm(self, village):
        return village.passes_threshold(self.threshold) or village.is_fresh_meat() or village.finished_rest(self.rest)

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

    def estimate_troops_needed(self, unit, estimated_capacity):
        return round(estimated_capacity/unit.haul)

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

    def is_attack_possible(self, villa, troops_map):
        """Evaluates if there enough troops to loot all
        village resources at the time of arrival with current troops.
        Returns dict {Unit_obj: number to send}
        """
        for unit_name, count in troops_map.items():
            if unit_name == 'spy':
                continue
            unit = self.units[unit_name]
            time_on_road = self.get_time_on_the_road(villa.dist_from_base, unit.speed)
            if villa.is_fresh_meat():   # No info about last_visited & remaining_capacity
                estimated_capacity = self.estimate_initial_capacity(villa)
                units_needed = self.estimate_troops_needed(unit, estimated_capacity)
            else:
                t_of_arrival = self.estimate_arrival(time_on_road)
                estimated_capacity = villa.estimate_capacity(t_of_arrival)
                units_needed = self.estimate_troops_needed(unit, estimated_capacity)
            if units_needed <= count:
                return {unit_name: units_needed}, time_on_road

        else: return

    def get_next_attack_target(self, troops_map):
        """Decides if nearest villages in self.queue could
         be attacked with existing amount of troops.
         Number of checked villages is based on self.depth.
         If it's possible to attack, returns coordinates and
         amount of troops, otherwise - None
         """
        #print("Have villages: ", self.villages)
        if self.queue:  # there is something to farm
            high_priority = self.queue[0]
            check = self.is_attack_possible(high_priority, troops_map)
            if check:   # tuple({unit_name:count}, t_on_road)
                #print("Sending high priority, items in queue: {}, first 15 villages in queue: {}".format(len(self.queue), self.queue[:15]))
                #print("Current troops map: ", troops_map)
                self.queue.remove(high_priority)
                return (high_priority.coords, check[0], check[1])
            else:
                next_priorities = self.queue[1:self.depth+1]
                if next_priorities:
                    for villa in next_priorities:
                        check = self.is_attack_possible(villa, troops_map)
                        if check:
                            #print("Sending 'depth' priority, items in queue: {}, first 15 villages in queue: {}".format(len(self.queue), self.queue[:15]))
                            #print("Current troops map: ", troops_map)
                            self.queue.remove(villa)
                            return (villa.coords, check[0], check[1])
        else:
            self.build_queue()
        return

    def update_villages(self, new_reports):
        """
        Updates self.villages with a new reports.
        Updates self.visited_villages with updated villages.
        Checks if some of visited villages can be placed in
        attack queue again (flush_visited_villages)
        """
        for coords, report in new_reports.items():
            if coords in self.villages:
                print("Villa before update: {}".format(self.villages[coords]))
                self.villages[coords].update_stats(report)
                print('Villa after update: {}'.format(self.villages[coords]))
                self.visited_villages.append(self.villages[coords])

        self.flush_visited_villages()

    def flush_visited_villages(self):
        """
        Updates self.queue with villages that could be farmed again.
        """
        ready_for_farm = [villa for villa in self.visited_villages if self.is_ready_for_farm(villa)]
        if ready_for_farm:
            print("Time: {}, going to flush the next villages: {}".format(time.ctime(), ready_for_farm))
        for villa in ready_for_farm:
            self.queue.append(villa)
            self.visited_villages.remove(villa)

        self.queue = sorted(self.queue, key=lambda x: x.dist_from_base)

    def update_villages_in_map(self):
        #print("Going to update next villages in map: ", self.villages)
        self.map.update_villages(self.villages)

    def init_units(self):
        units = {'axe': Unit('axe', 18, 10),
                 'light': Unit('light', 10, 80),
                 'heavy': Unit('heavy', 11, 50)}
        return units


class Observer(Thread):

    def __init__(self, parent_manager):
        Thread.__init__(self)
        self.manager = parent_manager


class AttackObserver(Observer):
    """
    Notifies 'parent' manager(Attack) about 2 events:
    1. Troops sent arrived in target village (need to update
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
        self.arrival_queue = []
        self.return_queue = []
        self.get_saved_attacks()

    def run(self):
        # to do: read about threading Events
        while self.manager.active:
            if self.someone_arrived():
                self.manager.new_battle_reports = True
            if self.someone_returned():
                self.manager.some_troops_returned = True
            time.sleep(1)
        self.save_registered_attacks()
        return

    def get_saved_attacks(self):
        f = shelve.open(self.data_file)
        if 'arrival_queue' in f:
            registered_arrivals = f['arrival_queue']
            now = time.mktime(time.gmtime())
            arrived = [t for t in registered_arrivals if t < now]
            if arrived:
                self.manager.new_battle_reports = True
            self.arrival_queue = [t for t in registered_arrivals if t > now]
        if 'return_queue' in f:
            registered_returns = f['return_queue']
            now = time.mktime(time.gmtime())
            self.return_queue = [t for t in registered_returns if t > now]
        f.close()

    def save_registered_attacks(self):
        f = shelve.open(self.data_file)
        f['arrival_queue'] = self.arrival_queue
        f['return_queue'] = self.return_queue
        f.close()

    def someone_arrived(self):
        time_gmt = time.mktime(time.gmtime())
        arrived = [t for t in self.arrival_queue if t <= time_gmt]
        if arrived:
            for value in arrived:
                self.arrival_queue.remove(value)
        return arrived

    def someone_returned(self):
        time_gmt = time.mktime(time.gmtime())
        returned = [t for t in self.return_queue if t <= time_gmt]
        if returned:
            for value in returned:
                self.return_queue.remove(value)
        return returned

    def register_attack(self, t_of_arrival, t_of_return):
        self.arrival_queue.append(t_of_arrival)
        self.return_queue.append(t_of_return)


class Unit:
    """Representation of TW unit.
    """

    def __init__(self, name, speed, haul):
        self.name = name
        self.speed = speed
        self.haul = haul

    def __str__(self):
        return "Unit:=>{0}, speed:=>{1}, haul:=>{2}".format(self.name, self.speed, self.haul)

    def __repr__(self):
        return self.__str__()
