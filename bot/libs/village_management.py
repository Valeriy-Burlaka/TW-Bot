import re
import json
import time
import random
import logging
from threading import Thread

from bot.libs.map_tools import MapStorage, MapParser, MapMath
from bot.libs.attack_management import Unit
import settings


class VillageManager(Thread):
    """
    Manages operations related to in-game types of villages:
    attacker's village (represented by PlayerVillage class) &
    target village (Bonus/Barbarian/other players villages,
    represented by TargetVillage class):

    1. Collaborates with RequestManager, MapParser, MapStorage, MapMath,
    TargetVillage to build mapping of target villages.
    2. Collaborates with MapStorage to update saved target villages.
    3. Collaborates with RequestManager, MapMath, PlayerVillage to build
    mapping of attacker's villages.
    4. Collaborates with RequestManager to update information about troops
    in PlayerVillages.
    5. Collaborates with AttackManager class by providing the next interfaces:

    get_attack_targets():
        returns mapping {(x_coordinate, y_coordinate): Village_object, ...}
    get_targets_by_id():
        returns mapping {attacker_id: [attack_target1, ...], ...}, where
        each attack_target is a ((x, y), int(distance_from_attacker))
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

    6. Provides the next interface method to change farming settings
    (e.g. list of attackers, troops which should be used):

    set_farming_villages(farm_with=None, use_def_to_farm=False,
                             heavy_is_def=False, t_limit_to_leave=4)
        Sets self.farming_villages & self.targets_by_id basing on input
        parameters & current self.player_villages,
    """

    def __init__(self, request_manager, lock, trusted_targets=None, map_depth=2,
                 storage_type='local_file', storage_file_name='map_data'):
        Thread.__init__(self)
        self.request_manager = request_manager
        self.lock = lock
        self.map_depth = map_depth
        self.trusted_targets = trusted_targets
        self.map_storage = MapStorage(storage_type, storage_file_name)
        self.map_parser = MapParser()
        self.player_villages = self.build_player_villages()
        self.target_villages = self.build_target_villages()
        self.farming_villages = {}
        self.targets_by_id = {}

    def get_attack_targets(self):
        return self.target_villages

    def get_targets_by_id(self):
        return self.targets_by_id

    def get_next_attacking_village(self):
        """
        Randomly decides which PlayerVillage from list of active
        attacking villages should attack next.
        Returns tuple(attacker_id, attacker_troops)
        """
        active_farming_villages = {villa_id: v for villa_id, v in
                                   self.farming_villages.items() if v.active}
        if active_farming_villages:
            attackers = list(active_farming_villages.values())
            next_attacker = random.choice(attackers)
            attacker_id = next_attacker.id
            attacker_troops = next_attacker.get_troops_count()
            return attacker_id, attacker_troops

    def disable_farming_village(self, villa_id):
        self.farming_villages[villa_id].active = False

    def update_troops_count(self, villa_id, troops_sent):
        """
        Updates attacker's (PlayerVillage) troops count according
        to amount of troops that were sent in attack.
        """
        self.farming_villages[villa_id].update_troops_count(troops_sent=troops_sent)

    def refresh_village_troops(self, villa_id):
        """
        Requests Games' train screen (where all troops for PlayerVillage
        are displayed) and passes it to given PlayerVillage to update
        troops count
        """
        if villa_id in self.farming_villages:
            train_screen_html = self._get_train_screen(villa_id)
            self.farming_villages[villa_id].update_troops_count(train_screen_html=train_screen_html)
            # since some troops have returned, try
            # to consider villa as attacker again.
            self.farming_villages[villa_id].active = True
            if not settings.DEBUG:
                time.sleep(random.random() * 3)

    def update_villages_in_storage(self, villages):
        self.map_storage.update_villages(villages)

    def build_player_villages(self):
        """
        Builds a mapping of PlayerVillage objects from 'overviews' Game screen
        """
        overviews_html = self._get_overviews_screen()
        villages_data = self._get_villages_data(overviews_html)

        logging.debug(villages_data)

        player_villages = {}
        for villa_data in villages_data:
            villa_id, villa_coords, villa_name = villa_data[0], villa_data[1], villa_data[2]
            player_village = PlayerVillage(villa_id, villa_coords, villa_name)
            player_villages[villa_id] = player_village

        logging.debug(player_villages)

        return player_villages

    def build_target_villages(self):
        """
        Returns mapping of valid target villages (that may be farmed):
        1. Retrieves previously stored villages
        2. Retrieves sectors_data for each potential attacker
        3. Composes mapping of target villages from all retrieved sectors.
        4. Creates new / uses saved Village objects for all valid targets.
        5. returns mapping {(x_coord, y_coord): Village_obj, ...}
        """
        target_villages = {}
        saved_villages = self.map_storage.get_saved_villages()
        distinct_farming_centers = [(player_village.coords, player_village.id)
                                    for player_village
                                    in self.player_villages.values()]
        map_data = self._get_map_data(distinct_farming_centers, self.map_depth)
        # filter out all villages except Barbarian/Bonus and players villages
        # explicitly marked as trusted targets
        map_data = {coords: village_data for coords, village_data in map_data.items()
                    if self._is_valid_target(village_data) or coords in self.trusted_targets}
        for coords, village_data in map_data:
            if coords in saved_villages:
                target_villages[coords] = saved_villages[coords]
                # Update info about village population
                target_villages[coords].population = village_data[3]
            else:
                target_villages[coords] = self._build_target_village(coords, village_data)

        logging.info("Villages collected upon map "
                     "initialization: {}".format(target_villages))

        return target_villages

    def set_farming_villages(self, farm_with=None, use_def_to_farm=False,
                             heavy_is_def=False, t_limit_to_leave=4):
        """
        Creates mapping of PlayerVillages that should be used as attackers.
        Configures attackers according to input parameters:

        farm_with: list of ids of PlayerVillages which should be used
        as attackers.
        use_def_to_farm: if set to 'True', all both offensive & defensive
        troops in PlayerVillages will be used to farm.
        heavy_is_def: if use_def_to_farm is set to 'False' & heavy_is_def
        is set to 'True', HeavyCavalry unit will be considered as defensive
        unit and will not be used to farm villages.
        t_limit_to_leave: time limit (hours) for troops to leave PlayerVillage.
        This parameter will define the maximum farming radius for each particular
        PlayerVillage. E.g.: if t_limit_to_leave was set to 4 hours &
        PlayerVillage has LightCavalry units, maximum farming radius will be set
        to 6 * 3 = 18 tiles (LC speed * t_limit)

        Method automatically invokes self.set_targets_by_attacker_id method to
        create a mapping of attack targets for each attacker.
        """
        if farm_with is not None:
            farming_villages = {villa_id: player_village for villa_id, player_village in
                                self.player_villages.items() if villa_id in farm_with}
        else:
            farming_villages = self.player_villages

        for player_village in farming_villages.values():
            player_village.set_troops_to_use(use_def_to_farm, heavy_is_def)
            html_data = self._get_train_screen(player_village.id)
            player_village.set_farm_radius(html_data, t_limit_to_leave)
            player_village.update_troops_count(train_screen_html=html_data)
            if not settings.DEBUG:
                time.sleep(random.random() * 3)

        for player_village in farming_villages.values():
            logging.info(str(player_village))

        self.farming_villages = farming_villages
        self.set_targets_by_attacker_id()

    def set_targets_by_attacker_id(self):
        """
        Returns a dict, where {key=attacker_id (PlayerVillage id): value =
        list of targets sorted ascending (nearest first), ...} and
        each attack target is a tuple((x, y), distance_from_attacker)
        """
        targets_by_id = {}
        for player_village in self.farming_villages.values():
            attacker_id = player_village.id
            attacker_coords = player_village.coords
            preferred_radius = player_village.radius
            targets_in_radius = MapMath.get_targets_in_radius(attacker_coords,
                                                              preferred_radius,
                                                              self.target_villages)
            targets_in_radius = sorted(targets_in_radius, key=lambda x: x[1])
            targets_by_id[attacker_id] = targets_in_radius

        event_msg = "AttackQueue: targets by id: {}".format(targets_by_id)
        logging.info(event_msg)

        for attacker_id, targets in targets_by_id.items():
            event_msg = "Attacker {id} has {c} villages in " \
                        "its farm radius".format(id=attacker_id, c=len(targets))

            logging.info(event_msg)

        self.targets_by_id = targets_by_id

    @staticmethod
    def _get_villages_data(html_data):
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
        while distinct_farming_centers: # list of farming centers
            # check_center: ((x_coord, y_coord), village_id))
            check_center = distinct_farming_centers[0]
            center_coords = check_center[0]
            center_x, center_y = center_coords[0], center_coords[1]
            center_id = check_center[1]
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
                    centers =[(corner, corner_id)]
                    # Delay between "user" requests of map overview
                    if not settings.DEBUG:
                        time.sleep(random.random() * 6)
                    area_data.update(self._get_map_data(centers, map_depth))

            map_data.update(area_data)

        return map_data

    @staticmethod
    def _filter_distinct_centers(current_attacker, centers, sectors_data):
        """
        Checks to which sector current attacker belongs and
        sorts out all attackers that also belong to the same sector.
        Returns a list of attacking centers that are not "neighbors"
        of a given attacker.
        """
        distinct_centers = []
        for sector in sectors_data:
            if current_attacker in sector:
                for center in centers:
                    center_coords = center[0]
                    if center_coords not in sector:
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
    def _build_target_village(villa_coords, village_data):
        """
        Constructs a Village obj from given data
        """
        id_ = int(village_data[0])
        # dot-separated str, e.g. "4.567" (=4567)
        population = village_data[3]
        population = int(population.replace('.', ''))
        if len(village_data) > 6:
            bonus = village_data[6][0]
            village = TargetVillage(villa_coords, id_, population, bonus)
        else:
            village = TargetVillage(villa_coords, id_, population)

        return village
    
    def _get_map_overview(self, village_id, x, y):
        if not settings.DEBUG:
            time.sleep(random.random() * 3)
        # Call to lock is not needed here, because map_overviews are
        # requested upon VillageManager init and thus are performed
        # synchronously.
        html_data = self.request_manager.get_map_overview(village_id, x, y)
        return html_data
    
    def _get_train_screen(self, villa_id):
        self.lock.acquire()
        train_screen_html = self.request_manager.get_train_screen(villa_id)
        self.lock.release()
        return train_screen_html

    def _get_overviews_screen(self):
        self.lock.acquire()
        overviews_screen_html = self.request_manager.get_overviews_screen()
        self.lock.release()
        return overviews_screen_html

    def _get_village_overview(self, villa_id):
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

    def __init__(self, id_, coords, name, flag=None):
        self.id = id_
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
            if unit_name == 'spy':
                continue
            if unit_name in troops_data:
                unit_speed = units[unit_name].speed
                # Per Game, speed is reversed value (minutes-per-tile),
                # so getting tiles-per-hour.
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


class TargetVillage:
    """
    Represents a single target village (Bonus/Barbarian or
    other player's village, considered as 'safe' target)
    Contains information and logic needed to make attack decision
    (remaining resource loot, mine levels, time when village
    was last visited ==> expected resource loot)
    Stores statistic about attacks {time_of_visit: looted_resources, ..}
    """

    def __init__(self, coords, id_, population, bonus=None):
        self.id = id_
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
            else:
                self.looted["total"] = looted
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
            if hours >= 8:
                hours = 8
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
