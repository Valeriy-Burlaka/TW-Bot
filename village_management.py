import re
import json
import time
import random
import os
import logging
from threading import Thread


class VillageManager(Thread):
    """
    Component responsible for getting and keeping information
    about player's village (troops, resources).
    Future improvements: subclass from Thread,
    extend for tracking building/hire queues, incoming attacks,
    making decisions about resources usage.
    """

    def __init__(self, request_manager, lock, main_id, farm_with, run_path,
                 use_def_to_farm=False, heavy_is_def=False, t_limit_to_leave=4):
        Thread.__init__(self)
        self.request_manager = request_manager
        self.lock = lock
        self.main_id = main_id
        self.farm_with = farm_with
        self.run_path = run_path
        self.player_villages = self.build_player_villages()
        self.t_limit = t_limit_to_leave
        self.farming_villages = self.get_farming_villages(use_def_to_farm,
                                                          heavy_is_def)

    def build_player_villages(self):
        """
        Builds a mapping of PlayerVillage objects from 'overviews' Game screen
        """
        overviews_html = self.request_manager.get_overviews_screen()
        with open(os.path.join(self.run_path, "overviews.html"), 'w') as f:
            f.write(overviews_html)
        villages_data = self.get_villages_data(overviews_html)
        print(villages_data)
        player_villages = {}
        for villa_data in villages_data:
            villa_id, villa_coords, villa_name = villa_data[0], villa_data[1], villa_data[2]
            pv = PlayerVillage(villa_id, villa_coords, villa_name)
            player_villages[villa_id] = pv
        print(player_villages)
        return player_villages

    def get_villages_data(self, html_data):
        """
        Parses "Overviews" game screen to extract player's villages.
        Returns list of tuples (int(villa_id), str(villa_name),
        tuple(villa_coordinates))
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
        active_farming_villages = {v_id: v for v_id, v in
                                   self.farming_villages.items() if v.active}
        if active_farming_villages:
            attackers = list(active_farming_villages.values())
            next_attacker = random.choice(attackers)
            attacker_id = next_attacker.id
            attacker_troops = next_attacker.get_troops_count()
            return (attacker_id, attacker_troops)
        else:
            return

    def disable_farming_village(self, villa_id):
        self.farming_villages[villa_id].active = False

    def update_troops_count(self, villa_id, troops_sent):
        self.farming_villages[villa_id].update_troops_count(troops_sent=troops_sent)

    def refresh_village_troops(self, villa_id):
        if villa_id in self.farming_villages:
            train_screen_html = self.get_train_screen(villa_id)
            self.farming_villages[villa_id].update_troops_count(train_screen_html=train_screen_html)
            self.farming_villages[villa_id].active = True    # since some troops have returned, try to consider villa as attacker again.
            time.sleep(random.random() * 3)

    def get_farming_villages(self, use_def, heavy_is_def):
        farming_villages = {v_id: pv for v_id, pv in
                            self.player_villages.items() if
                            v_id in self.farm_with}
        for pv in farming_villages.values():
            pv.set_troops_to_use(use_def, heavy_is_def)
            html_data = self.get_train_screen(pv.id)
            pv.set_farm_radius(html_data, self.t_limit)
            pv.update_troops_count(train_screen_html=html_data)
            time.sleep(random.random() * 3)

        for pv in farming_villages.values():
            logging.info(str(pv))

        return farming_villages

    def get_attackers(self):
        attackers = []
        for pv in self.farming_villages.values():
            attacker_data = (pv.id, pv.coords, pv.radius)
            attackers.append(attacker_data)

        return attackers

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

    def __init__(self, id, coords, name, flag=None):
        self.id = id
        self.coords = coords
        self.name = name
        self.flag = flag
        self.troops_to_use = []
        self.troops_count = {}
        self.radius = 0
        self.active = True

    def set_farm_radius(self, html_data, t_limit):
        troops_data = self.get_troops_data(html_data)
        units = Unit.build_units()
        speeds_list = []
        for unit_name in self.troops_to_use:
            if unit_name == 'spy': continue
            if unit_name in troops_data:
                unit_speed = units[unit_name].speed
                # Per Game, speed is reversed value (minutes-per-tile), so getting tiles-per-hour.
                unit_speed = round(60 / unit_speed, 3)
                speeds_list.append(unit_speed)

        max_radius = max(speeds_list) * t_limit
        self.radius = max_radius

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
        Returns dict containing all troops data for
        a given village (current & total)
        """
        data_ptrn = re.compile(r'UnitPopup.unit_data = '
                               r'([\w\W]+);[\s]*UnitPopup[\w\W]+')
        match = re.search(data_ptrn, html_data)
        troops_data = json.loads(match.group(1))
        return troops_data

    def get_troops_count(self):
        return self.troops_count

    def set_troops_to_use(self, use_def, heavy_is_def):
        if use_def:
            troops_group = Unit.get_def_names()
        else:
            troops_group = Unit.get_off_names()
            if heavy_is_def:
                troops_group.remove('heavy')

        self.troops_to_use = troops_group

    def __str__(self):
        return "PlayerVillage: id: {id}, coords: {coords}, " \
               "name: {name},\n current_troops: {troops}, " \
               "farm radius: {radius}".format(id=self.id,
                                              coords=self.coords,
                                              name=self.name,
                                              troops=self.troops_count,
                                              radius=self.radius)

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

    @classmethod
    def get_def_names(cls):
        return ['spear', 'sword', 'archer', 'axe', 'spy',
                'light', 'marcher', 'heavy']

    @classmethod
    def get_off_names(cls):
        return ['axe', 'spy', 'light', 'marcher', 'heavy']

    def __str__(self):
        return "Unit:=>{0}, speed:=>{1}, haul:=>{2}".format(self.name,
                                                            self.speed,
                                                            self.haul)

    def __repr__(self):
        return self.__str__()