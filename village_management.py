import re
import json
import time
import random
import os
import logging
from threading import Thread


class VillageManager(Thread):
    """

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

    @staticmethod
    def get_villages_data(html_data):
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
            # since some troops have returned, try
            # to consider villa as attacker again.
            self.farming_villages[villa_id].active = True
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

    @staticmethod
    def get_troops_data(html_data):
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


class Village:
    """
    Represents a single Bonus/Barbarian village.
    'Lives' in Map.
    """

    def __init__(self, coords, id, population, bonus=None):
        self.id = id
        self.coords = coords    # tuple (x,y)
        self.population = population    # int
        self.bonus = bonus  # str
        self.mine_levels = None  # list [wood, clay, iron], integers
        self.h_rates = None
        self.last_visited = None
        self.remaining_capacity = 0
        self.looted = {"total": 0, "per_visit": []}
        self.defended = False
        self.storage_limit = None
        self.base_defence = None

    def update_stats(self, attack_report):
        """
        Updates self basing on information of
        given attack_report object (includes recon info
        about haul looted, haul remaining, mine levels, etc.
        """
        self.last_visited = attack_report.t_of_attack
        if attack_report.defended:
            self.defended = True
        if attack_report.mine_levels:
            # A bit ugly assignment procedure, but it is needed
            # to prevent refreshing of mine levels to 0-level
            # when attacks are sent without scouts
            # (AR will set levels to [0,0,0])
            # No sane person would destroy mines in Barb villages,
            # so they likely could not decrease their lvl.
            new_levels = attack_report.mine_levels
            if self.mine_levels:
                for index, levels in enumerate(zip(self.mine_levels,
                                                   new_levels)):
                    old_level, new_level = levels[0], levels[1]
                    if new_level > old_level:
                        self.mine_levels[index] = new_level
            else:
                self.mine_levels = new_levels
            self.set_h_rates()
        if attack_report.remaining_capacity:
            self.remaining_capacity = attack_report.remaining_capacity
        if attack_report.storage_level:
            self.set_storage_limit(attack_report.storage_level)
        if attack_report.wall_level is not None:
            self.set_base_defence(attack_report.wall_level)
        if attack_report.looted_capacity:
            looted = attack_report.looted_capacity
            if self.looted["total"]:
                self.looted["total"] += looted
            else: self.looted["total"] = looted
            self.looted["per_visit"].append((self.last_visited, looted,))

    def set_h_rates(self):
        """Sets a village resource production
        h/rates basing on mines level & production bonus
        """
        if self.mine_levels:
            rates = self.get_mine_rates()
            self.h_rates = [rates[x] for x in self.mine_levels]
            if self.bonus:
                if "all resource type" in self.bonus:
                    self.h_rates = [round(x * 1.3) for x in self.h_rates]
                elif "wood" in self.bonus:
                    self.h_rates[0] *= 2
                elif "clay" in self.bonus:
                    self.h_rates[1] *= 2
                else:
                    self.h_rates[2] *= 2

    def set_storage_limit(self, storage_level):
        # limit * 3 types of resources
        self.storage_limit = self.get_storage_rates()[storage_level] * 3

    def set_base_defence(self, wall_lvl):
        self.base_defence = 20 + (wall_lvl * 50)

    def estimate_capacity(self, t_of_arrival):
        """
        Estimates village capacity at the moment
        when troops will arrive to it.
        """
        if self.h_rates:
            t_of_rest = t_of_arrival - self.last_visited
            hours = t_of_rest / 3600
            # There no chances that anybody in player's
            # area didn't visit target village over time.
            if hours >= 8: hours = 8
            estimated_capacity = sum(x * hours for x in self.h_rates)
            if self.remaining_capacity:
                estimated_capacity += self.remaining_capacity
            if self.storage_limit and estimated_capacity > self.storage_limit:
                estimated_capacity = self.storage_limit
        else:
            estimated_capacity = self.get_default_capacity()

        return round(estimated_capacity)

    def has_valuable_loot(self, rest):
        if self.h_rates and self.remaining_capacity:
            # How many hours village has rested before our last visit:
            if self.remaining_capacity / sum(self.h_rates) >= rest:
                return True
            else:
                return False

    def finished_rest(self, rest):
        if self.last_visited:
            time_gmt = time.mktime(time.gmtime())
            return time_gmt - self.last_visited > rest * 3600

    def get_default_capacity(self):
        """
        Roughly estimates village capacity basing on its .population
        """
        if self.population in range(1, 100):
            return 1200
        elif self.population in range(100, 200):
            return 2400
        elif self.population in range(200, 300):
            return 3200
        elif self.population in range(300, 400):
            return 4800
        elif self.population in range(400, 600):
            return 6400
        elif self.population in range(600, 800):
            return 8000
        else:
            return 16000

    @staticmethod
    def get_mine_rates():
        """returns list of h/rates based on info from game Help page.
        Index = mine_level, value = production hour rate.
        (http://help.tribalwars.net/wiki/Timber_camp)
        """
        rates = [5, 30, 35, 41, 47, 55, 64, 74, 86, 100, 117,
                 136, 158, 184, 214, 249, 289, 337, 391, 455,
                 530, 616, 717, 833, 969, 1127, 1311, 1525, 1774,
                 2063, 2400]

        return rates

    @staticmethod
    def get_storage_rates():
        rates = [500, 1000, 1229, 1512, 1859, 2285, 2810, 3454,
                 4247, 5222, 6420, 7893, 9705, 11932, 14670, 18037,
                 22177, 27266, 33523, 41217, 50675, 62305, 76604, 94184,
                 115798, 142373, 175047, 215219, 264611, 325337, 400000]

        return rates

    def __str__(self):
        info = "Village: \t\tcoords => {coords}, visited => {visit}, \n\
                remaining capacity => {remaining}, points => {pop}, " \
               "h-rates => {rates},\n\
                defended/base_defence? => {defended}/{base_def}, " \
               "total loot => {total},\n\
                last loot => {last}, " \
               "storage => {stor} ".format(coords=self.coords,
                                           visit=time.ctime(self.last_visited),
                                           remaining=self.remaining_capacity,
                                           pop=self.population,
                                           rates=self.h_rates,
                                           stor=self.storage_limit,
                                           defended=self.defended,
                                           base_def=self.base_defence,
                                           total=self.looted['total'],
                                           last=self.looted['per_visit'][-1:])

        return info

    def __repr__(self):
        return self.__str__()
