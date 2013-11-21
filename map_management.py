__author__ = 'Troll'

import re
import shelve
import time
import json
import random
from math import sqrt


class Map:
    """A collecton of Villages.
    Responsible for taking HTML map overview from
    RequestManager and building a mapping of Village objects.
    Responsible for giving a mapping of all villages in a particular range.
    Responsible for storing and updating villages in a local shelve file.
    """

    def __init__(self, base_x, base_y, request_manager, lock,  depth=2, mapfile='map'):
        self.request_manager = request_manager  # instance of RequestManager
        self.lock = lock
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
        print(x, y, 'depth:', depth)
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
                print('corners: ', sector_corners)
                for corner in sector_corners:
                    time.sleep(random.random() * 6)
                    self.build_villages(*corner, depth=depth)

        with open('villages_upon_map_init.txt', 'w') as f:
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
        if name == 0 or (name == 'Bonus village' and owner == '0'):
            return True
        else:
            return

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
    Represents a single village.
    'Lives' in Map.
    """

    def __init__(self, coords, id, population, bonus=None):
        self.id = id
        self.coords = coords    #tuple (x,y)
        self.population = population
        self.bonus = bonus  # str
        self.mine_levels = None #list [wood, clay, iron], integers
        self.h_rates = None
        self.last_visited = None
        self.remaining_capacity = 0
        self.looted = {"total": 0, "per_visit": []}

    def set_h_rates(self):
        """Sets a village resource production
        h/rates basing on mines level & production bonus
        """
        rates = self.get_rates_table()
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

    def estimate_capacity(self, t_of_arrival):
        """Estimates village capacity at the moment
        when troops will arrive to it.
        Returns int.
        """
        if self.last_visited:
            t_to_arrival = t_of_arrival - self.last_visited
        else:   # if no info about last_visit, count from now (GMT)
            t_to_arrival = t_of_arrival - time.mktime(time.gmtime())

        hours = t_to_arrival / 3600
        estimated_capacity = sum(x * hours for x in self.h_rates)
        if self.remaining_capacity:
            estimated_capacity += self.remaining_capacity

        return round(estimated_capacity)

    def update_stats(self, attack_report):
        """Updates self basing on information of
        given attack_report object (includes recon info
        about haul looted, haul remaining, mine levels, etc.
        """
        self.last_visited = attack_report.t_of_attack
        self.mine_levels = attack_report.mine_levels
        self.set_h_rates()
        self.remaining_capacity = attack_report.remaining_capacity

        looted = attack_report.looted_capacity
        self.looted["total"] += looted
        self.looted["per_visit"].append((self.last_visited, looted,))

    def is_fresh_meat(self):
        return not self.remaining_capacity and not self.last_visited

    def passes_threshold(self, threshold):
        return self.remaining_capacity > threshold

    def finished_rest(self, rest):
        if self.last_visited:
            time_gmt = time.mktime(time.gmtime())
            return time_gmt - self.last_visited > rest

    def get_rates_table(self):
        """returns list of h/rates based on info from game Help page.
        Index = mine_level, value = production hour rate.
        (http://help.tribalwars.net/wiki/Timber_camp)
        """
        rates = [5, 30, 35, 41, 47, 55, 64, 74, 86, 100, 117,
                 136, 158, 184, 214, 249, 289, 337, 391, 455,
                 530, 616, 717, 833, 969, 1127, 1311, 1525, 1774,
                 2063, 2400]

        return rates

    def __str__(self):
        info = """
               Village: coords: {coords}, remaining capacity: {remaining} \n
               H-rates: {rates}, Last visited: {visited}, population: {pop} \n
               Fresh?: {fresh}, Looted total: {total}\n
               """.format(coords=self.coords, remaining=self.remaining_capacity,
                          rates=self.h_rates, visited=time.ctime(self.last_visited),
                          pop=self.population, fresh=self.is_fresh_meat(),
                          total=self.looted['total'])
        return info

    def __repr__(self):
        return self.__str__()