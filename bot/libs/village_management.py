import re
import json
import time
import random
import logging

from bs4 import BeautifulSoup as Soup

from bot.libs.map_tools import MapStorage, MapMath
from bot.libs.attack_management import Unit


__all__ = ['VillageManager', 'TargetVillage', 'PlayerVillage']


class VillageManager:
    """
    Manages operations related to in-game types of villages:
    attacker's village (represented by PlayerVillage class) &
    target village (Bonus/Barbarian/other players villages,
    represented by TargetVillage class).
    Provides the next methods:

    build_player_villages(overviews_html):
        takes overviews screen (html string) and builds
        mapping of player's villages.
    build_target_villages(map_data, trusted_targets, server_speed):
        takes map data, list of trusted targets & server speed as
        input.
        filters map data (exclude non-neutral & non-trusted targets)
        and builds mapping of target villages.
    set_farming_village(attacker_id, train_screen, use_def, heavy)is_def):
        takes train screen (html string) for a given PlayerVillage
        & farming options.
        configures this PlayerVillage to act as farming village
    get_attack_targets():
        returns mapping {(x_coordinate, y_coordinate): Village_object, ...}
    get_next_attacking_village():
        randomly decides who will attack next
        returns tuple(attacker_id, attacker_troops)
    disable_farming_village(attacker_id):
        marks given village as inactive (so it will not be considered as
        the next possible attacker)
    update_troops_count(attacker_id, troops):
        updates given attacker's troops basing on amount of troops that
        were sent
    refresh_village_troops(attacker_id):
        requests 'fresh' village overview screen for a given attacker
        and updates its troops count
    update_villages_in_storage(villages)
        updates target villages saved in storage with a given mapping
        of target villages (those that were attacked & have more recent info)
    """

    def __init__(self, storage_type, storage_file_name):

        self.map_storage = MapStorage(storage_type, storage_file_name)
        self.player_villages = {}
        self.target_villages = {}
        self.farming_villages = {}

    def build_player_villages(self, overviews_html):
        """
        Builds a mapping of PlayerVillage objects from 'overviews' Game screen
        """
        villages_data = self._get_villages_data(overviews_html)

        logging.debug(villages_data)

        player_villages = {}
        for villa_data in villages_data:
            villa_id, villa_coords, villa_name = villa_data[0], villa_data[1], villa_data[2]
            player_village = PlayerVillage(villa_id, villa_coords, villa_name)
            player_villages[villa_id] = player_village

        logging.debug(player_villages)

        self.player_villages = player_villages

    def build_target_villages(self, map_data, trusted_targets, server_speed):
        """
        Returns mapping of valid target villages (that may be farmed):
        1. Retrieves previously stored villages
        2. Filters out 'invalid' (non-neutral & non-trusted) villages
        from given map data.
        3. Creates new / uses saved Village objects for all valid targets.
        4. sets result (mapping {(x_coord, y_coord): Village_obj, ...}) to
        self.target_villages.
        """
        target_villages = {}
        saved_villages = self.map_storage.get_saved_villages()

        # filter out all villages except Barbarian/Bonus and players villages
        # explicitly marked as trusted targets
        map_data = {coords: village_data for coords, village_data in map_data.items()
                    if self._is_valid_target(village_data) or coords in trusted_targets}
        for coords, village_data in map_data.items():
            if coords in saved_villages:
                target_villages[coords] = saved_villages[coords]
                # Update info about village population
                target_villages[coords].population = int(village_data[3])
            else:
                target_villages[coords] = self._build_target_village(coords,
                                                                     village_data,
                                                                     server_speed)

        logging.info("Villages collected upon map "
                     "initialization: {}".format(target_villages))

        self.target_villages = target_villages

    def set_farming_village(self, attacker_id, train_screen_html,
                            use_def_to_farm=False,
                            heavy_is_def=False):
        """
        Configures the PlayerVillage which should be used as attacker &
        sets attack targets for it.
        Input parameters:
        1) attacker_id = id of PlayerVillage which will be configured as
        attacker.
        2) train_screen_html = HTML data (string) which contains information
        about all troops for a given PlayerVillage.
        3) use_def_to_farm: if set to 'True', both offensive & defensive
        troops in PlayerVillages will be used to farm.
        4) heavy_is_def: if use_def_to_farm is set to 'False' & heavy_is_def
        is set to 'True', HeavyCavalry unit will be considered as defensive
        unit and will not be used to farm villages.

        """
        attacker = self.player_villages.get(attacker_id, None)
        if attacker is not None:
            attacker.set_troops_to_use(use_def_to_farm, heavy_is_def)
            attacker.update_troops_count(html_data=train_screen_html)
            attacker_targets = self._get_targets_for_attacker(attacker)
            attacker.set_attack_targets(attacker_targets)

            logging.info(str(attacker))
            event_msg = "Attacker {id} has {c} villages in " \
                        "its farm radius".format(id=attacker.id,
                                                 c=len(attacker.attack_targets))
            logging.info(event_msg)

            self.farming_villages[attacker_id] = attacker
        else:
            logging.error("Player Village with id {id} doesn't exist!".format(id=attacker_id))

    def get_attack_targets(self):
        return self.target_villages

    def get_next_attacking_village(self):
        """
        Randomly decides which PlayerVillage from list of active
        attacking villages should attack next.
        Returns tuple(attacker_id, attacker_troops, attacker_targets)
        """
        active_farming_villages = {villa_id: v for villa_id, v in
                                   self.farming_villages.items() if v.active}
        if active_farming_villages:
            attackers = list(active_farming_villages.values())
            next_attacker = random.choice(attackers)
            attacker_id = next_attacker.id
            attacker_troops = next_attacker.get_troops_count()
            attacker_targets = next_attacker.attack_targets
            return attacker_id, attacker_troops, attacker_targets

    def disable_farming_village(self, attacker_id):
        self.farming_villages[attacker_id].active = False

    def update_troops_count(self, attacker_id, troops_sent):
        """
        Updates attacker's (PlayerVillage) troops count according
        to amount of troops that were sent in attack.
        """
        attacker = self.farming_villages.get(attacker_id, None)
        if attacker is not None:
            attacker.update_troops_count(troops_sent=troops_sent)
        else:
            logging.error("Player Village with id {id} is not in list "
                            "of farming villages!".format(id=attacker_id))

    def refresh_village_troops(self, villa_id, train_screen_html):
        """
        Passes given train screen to PlayerVillage to update
        its troops
        """
        if villa_id in self.farming_villages:
            attacker = self.farming_villages[villa_id]
            attacker.update_troops_count(html_data=train_screen_html)
            # since some troops have returned, try
            # to consider villa as attacker again.
            self.farming_villages[villa_id].active = True

    def update_villages_in_storage(self, villages):
        self.map_storage.update_villages(villages)

    def _get_targets_for_attacker(self, attacker):
        """
        Asks MapMath for a list of targets for a given attacker
        (where each attack target is a tuple((x, y), distance_from_attacker))
        """
        attacker_coords = attacker.coords
        target_coords = self.target_villages.keys()
        targets_by_distance = MapMath.get_targets_by_distance(attacker_coords,
                                                              target_coords)
        return targets_by_distance

    @staticmethod
    def _get_villages_data(html_data):
        """
        Parses "Overviews" game screen to extract player's villages.
        Returns list of tuples (int(villa_id), str(villa_name),
        tuple(villa_coordinates))
        """
        villa_info_ptrn = re.compile("""(?P<id>\d{6})  # village id
                                        \W+  # closing quote, bracket,
                                             # possible space character
                                        (?P<name>[\w\s]+)  # village name
                                        \W  # bracket before coordinates
                                        (?P<xcoord>\d{3})  # village x
                                        \|  # delimiter between x & y
                                        (?P<ycoord>\d{3})  # village y
                                     """, re.VERBOSE)
        villages_data = []
        soup = Soup(html_data)
        villages_info = soup.findAll(id=re.compile('label_text_\d+'))
        for village in villages_info:
            text = str(village)
            data = re.search(villa_info_ptrn, text)
            village_id = int(data.group('id'))
            village_name = data.group('name').rstrip()
            village_coords = int(data.group('xcoord')), int(data.group('ycoord'))
            villages_data.append((village_id, village_coords, village_name))

        return villages_data

    @staticmethod
    def _is_valid_target(village_data):
        """
        Checks if village is Barbarian or Bonus without owner.
        """
        name = village_data[2]
        owner = village_data[4]
        if (name == 0 or name == "Bonus village") and owner == "0":
            return True
        else:
            return False

    @staticmethod
    def _build_target_village(villa_coords, village_data, server_speed):
        """
        Constructs a Village obj from given data
        """
        id_ = int(village_data[0])
        # dot-separated str, e.g. "4.567" (=4567)
        population = village_data[3]
        population = int(population.replace('.', ''))
        if len(village_data) > 6:
            bonus = village_data[6][0]
            village = TargetVillage(villa_coords, id_, population,
                                    bonus=bonus,
                                    server_speed=server_speed)
        else:
            village = TargetVillage(villa_coords, id_, population,
                                    server_speed=server_speed)

        return village


class PlayerVillage:
    """
    Component responsible for holding & updating info
    about troops in player's villages.

    """

    def __init__(self, id_, coords, name, flag=None):
        self.id = id_
        self.coords = coords
        self.name = name
        self.flag = flag
        self.troops_to_use = []
        self.troops_count = {}
        self.attack_targets = []
        self.active = True

    def update_troops_count(self, html_data=None, troops_sent=None):
        if html_data:
            troops_data = self.get_troops_data(html_data)
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

    def set_attack_targets(self, attack_targets):
        self.attack_targets = attack_targets

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
               "name: {name},\n current_troops: {troops}, ".format(id=self.id,
                                                                   coords=self.coords,
                                                                   name=self.name,
                                                                   troops=self.troops_count,)

    def __repr__(self):
        return self.__str__()


class TargetVillage:
    """
    Represents a single target village (Bonus/Barbarian or
    other player's village, considered as 'safe' target)
    Contains information and logic needed to make attack decision
    (remaining resource loot, mine levels, time when village
    was last visited ==> expected resource loot)
    Stores history about last 10 attacks.

    Provides the next interface methods:

    update_stats(attack_report):
        takes AttackReport object and update information
        about self basing on AR data
    estimate_capacity(t_of_arrival):
        estimates amount of village resources at the moment
        of troops arrival.
    has_valuable_loot(rest_interval):
        decides if village can be attacked again, without
        giving it time to rest.
    finished_rest(rest_interval):
        decides if village has finished to "rest" basing
        on the time of last visit.
    """

    def __init__(self, coords, id_, population, bonus=None, server_speed=1):
        self.id = id_
        self.coords = coords    # tuple (x,y)
        self.population = population
        self.bonus = bonus
        self.rate_multiplier = server_speed
        self.mine_levels = None
        self.h_rates = None
        self.last_visited = None
        self.remaining_capacity = 0
        self.total_loot = 0
        self.visits_history = []
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
        self.defended = attack_report.defended
        if attack_report.mine_levels:
            if self.mine_levels:
                # No sane person would destroy mines in Barb villages,
                # so they likely could not decrease their lvl.
                for index, level in enumerate(attack_report.mine_levels):
                    if level > self.mine_levels[index]:
                        self.mine_levels[index] = level
            else:
                self.mine_levels = attack_report.mine_levels
            self._set_h_rates()
        if attack_report.remaining_capacity is not None:
            self.remaining_capacity = attack_report.remaining_capacity
        if attack_report.storage_level:
            self._set_storage_limit(attack_report.storage_level)
        if attack_report.wall_level is not None:
            self._set_base_defence(attack_report.wall_level)
        if attack_report.looted_capacity:
            self.total_loot += attack_report.looted_capacity
            self._update_visits_history(attack_report.looted_capacity,
                                        attack_report.t_of_attack)

    def estimate_capacity(self, t_of_arrival):
        """
        Estimates village capacity at the moment
        when troops will arrive to it.
        """
        if self.h_rates:
            t_of_rest = t_of_arrival - self.last_visited
            hours = t_of_rest / 3600
            # There are no chances that anybody in player's
            # area didn't visit target village over time.
            if hours >= 8:
                hours = 8
            estimated_capacity = sum(x * hours for x in self.h_rates)
            if self.remaining_capacity:
                estimated_capacity += self.remaining_capacity
            if self.storage_limit and estimated_capacity > self.storage_limit:
                estimated_capacity = self.storage_limit
        else:
            estimated_capacity = self._get_default_capacity()

        return round(estimated_capacity)

    def has_valuable_loot(self, rest):
        if self.h_rates and self.remaining_capacity:
            # Not needed to wait until village will rest: there
            # left enough resources to loot it again.
            if self.remaining_capacity / sum(self.h_rates) >= rest:
                return True
            else:
                return False

    def finished_rest(self, rest):
        if self.last_visited:
            time_gmt = time.mktime(time.gmtime())
            return time_gmt - self.last_visited > rest * 3600

    def _set_h_rates(self):
        """
        Sets a village resource production h/rates basing
        on mines level, production bonus & server speed.
        """
        if self.mine_levels:
            rates = self._get_mine_rates()
            h_rates = [int(rates[x] * self.rate_multiplier)
                       for x in self.mine_levels]
            if self.bonus:
                if "all resource" in self.bonus:
                    h_rates = [round(x * 1.3) for x in h_rates]
                elif "wood" in self.bonus:
                    h_rates[0] *= 2
                elif "clay" in self.bonus:
                    h_rates[1] *= 2
                else:
                    h_rates[2] *= 2
            self.h_rates = h_rates

    def _set_storage_limit(self, storage_level):
        # limit * 3 types of resources
        self.storage_limit = self._get_storage_rates()[storage_level] * 3

    def _set_base_defence(self, wall_lvl):
        self.base_defence = 20 + (wall_lvl * 50)

    def _update_visits_history(self, looted, t_of_attack):
        """
        Keeps the record about last 10 attacks
        """
        self.visits_history.insert(0, (t_of_attack, looted))
        if len(self.visits_history) > 10:
            self.visits_history.pop()

    def _get_default_capacity(self):
        """
        Roughly estimates village capacity basing on its .population
        """
        if self.population in range(1, 50):
            return 600
        elif self.population in range(50, 100):
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
    def _get_mine_rates():
        """
        Returns list of mines h/rates.
        Index = mine_level, value = production hour rate.
        (http://help.tribalwars.net/wiki/Timber_camp)
        """
        rates = [5, 30, 35, 41, 47, 55, 64, 74, 86, 100, 117,
                 136, 158, 184, 214, 249, 289, 337, 391, 455,
                 530, 616, 717, 833, 969, 1127, 1311, 1525, 1774,
                 2063, 2400]

        return rates

    @staticmethod
    def _get_storage_rates():
        """
        http://help.tribalwars.net/wiki/Warehouse
        """
        rates = [1000, 1229, 1512, 1859, 2285, 2810, 3454,
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
                                           total=self.total_loot,
                                           last=self.visits_history)

        return info

    def __repr__(self):
        return self.__str__()
