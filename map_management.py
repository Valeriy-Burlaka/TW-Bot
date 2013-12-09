__author__ = 'Troll'

import re
import shelve
import time
import json
import random
from math import sqrt
from data_management import write_log_message


class Map:
    """A collecton of Villages.
    Responsible for taking HTML map overview from
    RequestManager and building a mapping of Village objects.
    Responsible for giving a mapping of all villages in a particular range.
    Responsible for storing and updating villages in a local shelve file.
    """

    def __init__(self, base_x, base_y, request_manager, lock, run_path, events_file, depth=2, mapfile='map'):
        self.request_manager = request_manager  # instance of RequestManager
        self.lock = lock
        self.run_path = run_path
        self.events_file = events_file
        self.villages = {}  # Will be {(x,y): {'village': Village, 'distance': int}
        self.mapfile = mapfile
        self.build_villages(base_x, base_y, depth)
        self.get_saved_villages()

    def get_saved_villages(self):
        """Searches for already existing villages in a local
        shelve file and updates self.villages if any.
        """
        f = shelve.open(self.mapfile)
        if 'villages' in f:
            still_valid = {}
            for coords, village in f['villages'].items():
                if coords in self.villages: # Saved village remained Bonus/Barbarian
                    self.villages[coords] = village  #Update with saved data
                    still_valid[coords] = village
            f['villages'] = still_valid
        f.close()

    def update_villages(self, villages):
        """Updates info about attacked villages in self.villages
        and in mapfile.
        """
        f = shelve.open(self.mapfile)
        if 'villages' in f:
            saved_villages = f['villages']
        else:
            saved_villages = {}
        for coords, village in villages.items():
            saved_villages[coords] = village
            self.villages[coords] = village
        f['villages'] = saved_villages
        f.close()

    def build_villages(self, x, y, depth):
        """Extracts village's data from sector data.
        Constructs Village objects with villages data.
        If depth > 1, requests sector's corners & recursively repeats
        Villages construction using corners as new start point.
        """
        depth -= 1
        event_msg = "Started to build villages from ({x},{y}) base point. Map depth={depth}".format(x=x,y=y,depth=depth)
        write_log_message(self.events_file, event_msg)
        map_html = self.get_map_overview(x, y)
        sectors = self.get_map_data(map_html)   # list of dicts, each dict represents 1 sector
        for sector in sectors:
            sector_x = sector['x']
            sector_y = sector['y']
            sector_coords = []  # hold coords of villages found, need to determine sector's corners
            sector_villages = sector['data']['villages']    # can be either list of dicts or dict of dicts
            # Some fun below: there are cases, when game stores sector villages in different data types
            # index is x coordinate, value is a dict of villages which lie on a y axis for given x.
            if isinstance(sector_villages, list):
                sector_gen = enumerate(sector_villages)
            # key is x coordinate, value is a dict of villages which lie on a y axis for given x.
            elif isinstance(sector_villages, dict):
                sector_gen = sector_villages.items()

            for x, y_axis in sector_gen:
                x = int(x)
                for y, village_data in y_axis.items():
                    if self.is_valid(village_data): # check if village is Bonus/Barbarian
                        villa_x = sector_x + x
                        villa_y = sector_y + int(y)
                        villa_coords = (villa_x, villa_y)
                        sector_coords.append(villa_coords)
                        if not villa_coords in self.villages:
                            village = self.get_village(villa_coords, village_data)
                            self.villages[villa_coords] = village

            if depth:
                sector_corners = self.get_sector_corners(sector_coords)
                event_msg = "Calculated the next sector corners: {}".format(sector_corners)
                write_log_message(self.events_file, event_msg)
                for corner in sector_corners:
                    time.sleep(random.random() * 6)
                    self.build_villages(*corner, depth=depth)

        with open("{run_path}/villages_upon_map_init.txt".format(run_path=self.run_path), 'w') as f:
            f.write(str(self.villages))

    def get_map_overview(self, x, y):
        time.sleep(random.random() * 3)
        self.lock.acquire()
        html_data = self.request_manager.get_map_overview(x, y)
        self.lock.release()
        return html_data

    def get_sector_corners(self, sector_coords):
        """
        Determines sector's corner points.
        Returns list of 4 points ( [(x=min,y=min), (x=max, y=max), etc.])
        """
        corners = []
        sector_coords = sorted(sector_coords)
        min_min = sector_coords[0]
        max_max = sector_coords[-1]
        corners.extend([min_min, max_max])
        w_min_x = [x for x in sector_coords if x[0] == min_min[0]]
        if len(w_min_x) > 1:    # if this village is not single on it's axis
            min_max = sorted(w_min_x)[-1]
            corners.append(min_max)
        w_max_x = [x for x in sector_coords if x[0] == max_max[0]]
        if len(w_max_x) > 1:
            max_min = sorted(w_max_x)[0]
            corners.append(max_min)

        return corners

    def get_village(self, villa_coords, village_data):
        """Constructs a Village obj from given data
        """
        id = int(village_data[0])
        population = village_data[3]    # str, e.g. "4.567" (4567)
        population = int(population.replace('.', ''))
        if len(village_data) > 6:
            bonus = village_data[6][0]
            village = Village(villa_coords, id, population, bonus)
        else:
            village = Village(villa_coords, id, population)

        return village

    def is_valid(self, village_data):
        """Checks if village is Barbarian or Bonus
        without owner. Returns True/False
        """
        name = village_data[2]
        owner = village_data[4]
        # Barbarian or Bonus w/o owner
        if (name == 0 or name == "Bonus village") and owner == "0":
            return True
        else:
            return False

    def calculate_distance(self, source_coords, target_coords):
        x = target_coords[0]
        y = target_coords[1]
        side_x = abs(source_coords[0] - x)
        side_y = abs(source_coords[1] - y)
        distance = sqrt(side_x**2 + side_y**2)
        return round(distance, 2)

    def get_map_data(self, html_data):
        """Returns dict containing sector data"""
        ptrn = re.compile('TWMap.sectorPrefech = ([\W\w]+?\]);')    # sectors data
        match = re.search(ptrn, html_data)
        js_res = match.group(1) # json string
        res = json.loads(js_res)
        return res

    def get_targets_in_radius(self, radius, source_coords):
        targets = []
        for coords, villa in self.villages.items():
            distance = self.calculate_distance(source_coords, coords)
            if distance <= radius: targets.append((coords, distance))

        return targets


class Village:
    """
    Represents a single Bonus/Barbarian village.
    'Lives' in Map.
    """

    def __init__(self, coords, id, population, bonus=None):
        self.id = id
        self.coords = coords    #tuple (x,y)
        self.population = population    # int
        self.bonus = bonus  # str
        self.mine_levels = None #list [wood, clay, iron], integers
        self.h_rates = None
        self.last_visited = None
        self.remaining_capacity = 0
        self.looted = {"total": 0, "per_visit": []}
        self.defended = False
        self.storage_limit = None
        self.base_defence = None

    def update_stats(self, attack_report):
        """Updates self basing on information of
        given attack_report object (includes recon info
        about haul looted, haul remaining, mine levels, etc.
        """
        self.last_visited = attack_report.t_of_attack
        if attack_report.defended:
            self.defended = True
        if attack_report.mine_levels:
            # A bit ugly assignment procedure, but it is needed to prevent refreshing
            # of mine levels to 0-level when attacks are sent without scouts (AR will set levels to [0,0,0])
            # No sane person would destroy mines in Barb villages, so they likely could not decrease their lvl.
            new_levels = attack_report.mine_levels
            if self.mine_levels:
                for index, levels in enumerate(zip(self.mine_levels, new_levels)):
                    old_level, new_level = levels[0], levels[1]
                    if new_level > old_level: self.mine_levels[index] = new_level
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
        self.storage_limit = self.get_storage_rates()[storage_level] * 3    # limit * 3 types of resources

    def set_base_defence(self, wall_lvl):
        self.base_defence = 20 + (wall_lvl * 50)

    def estimate_capacity(self, t_of_arrival):
        """Estimates village capacity at the moment
        when troops will arrive to it.
        """
        if self.h_rates:
            t_of_rest = t_of_arrival - self.last_visited
            hours = t_of_rest / 3600
            # There no chances that anybody in player's area didn't visit target village over time.
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
        """Roughly estimates village capacity basing on its .population
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

    def get_mine_rates(self):
        """returns list of h/rates based on info from game Help page.
        Index = mine_level, value = production hour rate.
        (http://help.tribalwars.net/wiki/Timber_camp)
        """
        rates = [5, 30, 35, 41, 47, 55, 64, 74, 86, 100, 117,
                 136, 158, 184, 214, 249, 289, 337, 391, 455,
                 530, 616, 717, 833, 969, 1127, 1311, 1525, 1774,
                 2063, 2400]

        return rates

    def get_storage_rates(self):
        rates = [500, 1000, 1229, 1512, 1859, 2285, 2810, 3454,
                 4247, 5222, 6420, 7893, 9705, 11932, 14670, 18037,
                 22177, 27266, 33523, 41217, 50675, 62305, 76604, 94184,
                 115798, 142373, 175047, 215219, 264611, 325337, 400000]

        return rates


    def __str__(self):
        info = "Village: \t\tcoords => {coords}, visited => {visit}, \n\
                remaining capacity => {remaining}, points => {pop}, h-rates => {rates},\n\
                defended/base_defence? => {defended}/{base_def}, total loot => {total},\n\
                last loot => {last}, storage => {stor} ".format(coords=self.coords, visit=time.ctime(self.last_visited),
                                                                remaining=self.remaining_capacity,
                                                                pop=self.population, rates=self.h_rates, stor=self.storage_limit,
                                                                defended=self.defended, base_def=self.base_defence,
                                                                total=self.looted['total'], last=self.looted['per_visit'][-1:])

        return info

    def __repr__(self):
        return self.__str__()