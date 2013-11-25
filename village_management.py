__author__ = 'Troll'

import re
import json
import time
import random
from threading import Thread
from data_management import write_log_message

class VillageManager(Thread):
    """
    Component responsible for getting and keeping information
    about player's village (troops, resources).
    Future improvements: subclass from Thread,
    extend for tracking building/hire queues, incoming attacks,
    making decisions about resources usage.
    """

    def __init__(self, request_manager, lock, main_id, farm_with, events_file,
                 use_def_to_farm=False, heavy_is_def=False, t_limit_to_leave=4):
        Thread.__init__(self)
        self.request_manager = request_manager
        self.lock = lock
        self.main_id = main_id
        self.farm_with = farm_with
        self.events_file = events_file
        self.player_villages = self.build_player_villages(use_def_to_farm, heavy_is_def)
        self.t_limit = t_limit_to_leave
        self.farming_villages = self.get_farming_villages()

    def build_player_villages(self, use_def, heavy_is_def):
        """
        Builds a mapping of PlayerVillage objects from 'overviews' screen
        """
        overviews_html = self.request_manager.get_overviews_screen()
        time.sleep(0.1)
        villages_data = self.get_villages_data(overviews_html)
        player_villages = {}
        for villa_data in villages_data:
            villa_id, villa_coords, villa_name = villa_data[0], villa_data[1], villa_data[2]
            time.sleep(random.random() * 3)
            html_data = self.get_train_screen(villa_id)
            pv = PlayerVillage(villa_id, villa_coords, villa_name, html_data, use_def, heavy_is_def)
            player_villages[villa_id] = pv

        return player_villages

    def get_villages_data(self, html_data):
        """
        Parses "Overviews" game screen to extract player's villages.
        Returns list of tuples (int(villa_id), str(villa_name), tuple(villa_coordinates))
        """
        villa_info_ptrn = re.compile(r'<span id="label_text_(\d+)">([\W\w]+?)\((\d{3})\|(\d{3})')
        villages_data = re.findall(villa_info_ptrn, html_data)
        for i, village_data in enumerate(villages_data):
            villa_id = int(village_data[0])
            villa_name = village_data[1].rstrip()
            villa_x, villa_y = int(village_data[2]), int(village_data[3])
            villages_data[i] = (villa_id, (villa_x, villa_y), villa_name)

        return villages_data

    def get_next_attacking_village(self):
        active_farming_villages = {v_id: v for v_id, v in self.farming_villages.items() if v.active}
#        print("VM: active farmers: ", active_farming_villages)
        if active_farming_villages:
            attackers = list(active_farming_villages.values())
            next_attacker = random.choice(attackers)
            attacker_id = next_attacker.id
            attacker_troops = next_attacker.get_troops_count()
            return (attacker_id, attacker_troops)
        else:
            return

    def disable_farming_village(self, villa_id):
        self.player_villages[villa_id].active = False

    def update_troops_count(self, villa_id, troops_sent):
        pv = self.player_villages[villa_id]
        pv.update_troops_count(troops_sent=troops_sent)
        self.player_villages[villa_id] = pv

    def refresh_village_troops(self, ids):
        for villa_id in ids:
            time.sleep(random.random() * 3)
            train_screen_html = self.get_train_screen(villa_id)
            pv = self.player_villages[villa_id]
            pv.update_troops_count(train_screen_html=train_screen_html)
            pv.active = True    # since some troops have returned, try to consider villa as attacker again.
            self.player_villages[villa_id] = pv

    def get_farming_villages(self):
        farming_villages = {v_id: pv for v_id, pv in self.player_villages.items() if v_id in self.farm_with}
        for pv in farming_villages.values():
            pv.set_preferred_farm_radius(self.t_limit)

        for pv in farming_villages.values():
            event_msg = """{pv}.
                            Farm radius: {radius}.
                            Total troops/looting capacity: {troops}/{loot}""".format(pv=pv, radius=pv.radius,
                                                                                    troops=pv.total_troops_count,
                                                                                    loot=pv.total_looting_capacity)
            print(event_msg)
            write_log_message(self.events_file, event_msg)

        return farming_villages

    def get_train_screen(self, villa_id):
        self.lock.acquire()
        train_screen_html = self.request_manager.get_train_screen(villa_id)
        self.lock.release()
        return train_screen_html

    def get_overviews_screen(self):
        self.lock.acquire()
        overviews_screen_html = self.request_manager.get_overviews_screen()
        self.lock.release()
        return overviews_screen_html

    def get_village_overview(self, villa_id):
        self.lock.acquire()
        village_overview = self.request_manager.get_village_overview(villa_id)
        self.lock.release()
        return village_overview

class PlayerVillage:
    """
    Component for holding & updating info about player's villages.
    In current implementation, provides only information about
    troops.
    """

    def __init__(self, id, coords, name, train_screen_html, use_def, heavy_is_def, flag=None):
        self.id = id
        self.coords = coords
        self.name = name
        self.flag = flag
        self.troops_to_use = self.get_troops_group(use_def, heavy_is_def)
        self.units = self.build_units()
        self.troops_data_on_init = self.get_troops_data(train_screen_html)
        self.troops_count = {}
        self.update_troops_count(train_screen_html=train_screen_html) # current troops in village
        self.active = True

    def set_preferred_farm_radius(self, t):
        """
        Tries to find the best farm radius for a given village, returns int.
        Steps:
        1. Gets total troops count (in-village, returning, etc.) from a train screen HTML.
        2. Calculates total looting capacity for each speed value (e.g. village has
        1000 axes & 1000 swords, then speed 18 has 10000 total looting capacity,
        speed 22 has 15000 looting capacity).
        3. Calculates density (% in total village looting capacity) for each speed value.
        4. Gets a sum of each (speed * t * speed_density), where t is a maximum hours
        for troops to live the village.

        Thus, for example, if we consider a village, that mostly has slow units, their speed
        density will form the majority of farm radius and we'll mitigate the chance of sending
        slow units to a 'far lands'. Additionally, we will try to use slowest units
        first when choosing an attack target in AttackQueue.
        """
        print(self.id, self.name)
#        print("troops to use:", self.troops_to_use)
#        print("troops count:", self.troops_count)
        total_troops_count = {}
        for unit_name in self.troops_to_use:
            if unit_name == 'spy': continue
            if unit_name in self.troops_data_on_init:
                unit = self.units[unit_name]
                count = int(self.troops_data_on_init[unit_name]['all_count'])
                total_troops_count[unit] = count

        self.total_troops_count = total_troops_count
        total_looting_capacity = sum((unit.haul * count for unit, count in total_troops_count.items()))
        self.total_looting_capacity = total_looting_capacity
        capacity_by_speed = {}
        for unit, count in total_troops_count.items():
            if unit.speed in capacity_by_speed:
                capacity_by_speed[unit.speed] += unit.haul * count
            else:
                capacity_by_speed[unit.speed] = unit.haul * count

        radius = 0
        for speed, amount in capacity_by_speed.items():
            speed = round(60 / speed, 3)  # unit.speed = minutes per tile, so getting tiles-per-hour value here.
            speed_radius = speed * t
            try:
                speed_density = round(amount / total_looting_capacity, 3)
                radius += speed_radius * speed_density
            except ZeroDivisionError:   # means that total looting capacity = 0
                radius = 0
                break

        self.radius = round(radius, 2)

    def build_units(self):
        return Unit.build_units()

    def update_troops_count(self, train_screen_html=None, troops_sent=None):
        if train_screen_html:
            troops_data = self.get_troops_data(train_screen_html)
            troops_count = {}
            for unit_name in self.troops_to_use:
                if unit_name in troops_data:
                    count = int(troops_data[unit_name]['available'])
                    troops_count[unit_name] = count

            self.troops_count = troops_count
        if troops_sent:
            if self.troops_count:
                for name, count in troops_sent.items():
                    self.troops_count[name] -= count

    def get_troops_data(self, html_data):
        """
        Returns dict containing all troops data for a given village (current & total)
        """
        data_ptrn = re.compile(r'UnitPopup.unit_data = ([\w\W]+);[\s]*UnitPopup[\w\W]+')
        match = re.search(data_ptrn, html_data)
        if not match: raise Exception('Unable to get troops data!')
        troops_data = json.loads(match.group(1))
        return troops_data

    def get_troops_count(self):
        return self.troops_count

    def get_troops_group(self, use_def, heavy_is_def):
        if use_def:
            troops_group = ['spear', 'sword', 'archer', 'axe', 'spy', 'light', 'marcher', 'heavy']
        else:
            troops_group = ['axe', 'spy', 'light', 'marcher', 'heavy']
            if heavy_is_def:
                troops_group.remove('heavy')
        return troops_group

    def __str__(self):
        str_villa = "PlayerVillage: id: {id}, coords: {coords}, name: {name},\n current_troops: {troops}"
        return str_villa.format(id=self.id, coords=self.coords, name=self.name, troops=self.troops_count)

    def __repr__(self):
        return self.__str__()


class Unit:
    """Representation of TW unit.
    """

    def __init__(self, name, attack, speed, haul):
        self.name = name
        self.attack = attack
        self.speed = speed
        self.haul = haul

    @classmethod
    def build_units(self):
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

    def __str__(self):
        return "Unit:=>{0}, speed:=>{1}, haul:=>{2}".format(self.name, self.speed, self.haul)

    def __repr__(self):
        return self.__str__()