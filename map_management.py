__author__ = 'Troll'

import re
import shelve
import time
import json
from math import sqrt


class Map:
    """A collecton of Villages.
    Responsible for taking HTML map overview from
    RequestManager and building a mapping of Village objects.
    Responsible for giving a mapping of all villages in a particular range.
    Responsible for storing and updating villages in a local shelve file.
    """

    def __init__(self, x, y, request_manager, depth=2, mapfile='map'):
        self.request_manager = request_manager  # instance of RequestManager
        self.villages = {}  # Will be {(x,y): {'village': Village, 'distance': int}
        self.mapfile = mapfile
        self.base_x = x
        self.base_y = y
        self.build_villages(x, y, depth)
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
                    distance = self.calculate_distance(coords)
                    self.villages[coords] = {"village":village, "distance": distance}   #Update with saved data
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
        for coords, v_data in villages.items():
            # Not storing distance in shelve: f['villages'] = {(x,y): Village, ..}
            saved_villages[coords] = v_data
            self.villages[coords]['village'] = v_data
        f['villages'] = saved_villages
        f.close()

    def build_villages(self, x, y, depth):
        """Extracts village's data from sector data.
        Constructs Villages and fills self.villages.
        If depth > 1, requests sector's data & repeats Villages
        construction for sector's corners recursively.
        """
        depth -= 1
        map_html = self.request_manager.get_map_overview(x, y)
        sectors = self.get_map_data(map_html)   # list of dicts, each dict represents 1 sector
        for sector in sectors:
            sector_x = sector['x']
            sector_y = sector['y']
            sector_coords = []  # hold coords of villages found, need to determine sector's corners
            sector_villages = sector['data']['villages']    # list, index = relative x coord.
            for x, y_axis in enumerate(sector_villages): # y_axis is a dict of villages
                for y, village_data in y_axis.items():
                    if self.is_valid(village_data): # check if village is Bonus/Barbarian
                        villa_x = sector_x + x
                        villa_y = sector_y + int(y)
                        villa_coords = (villa_x, villa_y)
                        sector_coords.append(villa_coords)
                        if not villa_coords in self.villages:
                            village = self.get_village(villa_coords, village_data)
                            distance = self.calculate_distance(villa_coords)
                            self.villages[villa_coords] = {"village":village, "distance":distance}

            if depth:
                sector_corners = self.get_sector_corners(sector_coords)
                for corner in sector_corners:
                    self.build_villages(*corner, depth=depth)

    def get_sector_corners(self, sector_coords):
        """Sorts given list of sector coords to determine
        corner points.
        Returns list of 4 points ( [(x=min,y=min), (x=max, y=max), etc.])
        """
        corners = []
        sorted_coords = sorted(sector_coords)
        min_min = sorted_coords[0]
        max_max = sorted_coords[-1]
        corners.extend([min_min, max_max])
        w_min_x = [x for x in sorted_coords if x[0] == min_min[0]]
        if len(w_min_x) > 1:    # if this village is not single on it's axis
            min_max = sorted(w_min_x)[-1]
            corners.append(min_max)
        w_max_x = [x for x in sorted_coords if x[0] == max_max[0]]
        if len(w_max_x) > 1:
            max_min = sorted(w_max_x)[0]
            corners.append(max_min)

        return corners

    def get_village(self, villa_coords, village_data):
        """Constructs a Village obj from given data
        """
        id = int(village_data[0])
        if len(village_data) > 6:
            bonus = village_data[6][0]
            village = Village(villa_coords, id, bonus)
        else:
            village = Village(villa_coords, id)

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

    def calculate_distance(self, coords):
        x = coords[0]
        y = coords[1]
        side_x = abs(self.base_x - x)
        side_y = abs(self.base_y - y)
        distance = sqrt(side_x**2 + side_y**2)
        return round(distance, 2)

    def get_map_data(self, html_data):
        """Returns dict containing sector data"""
        ptrn = re.compile('TWMap.sectorPrefech = ([\W\w]+?\]);')    # sectors data
        match = re.search(ptrn, html_data)
        js_res = match.group(1) # json string
        res = json.loads(js_res)
        return res

    def get_villages_in_range(self, distance):
        in_range = {key:value for key, value in self.villages.items() if value["distance"] <= distance}
        return in_range


class Village:
    """
    Represents a single village.
    'Lives' in Map.
    """

    def __init__(self, coords, id, bonus=None):
        self.id = id
        self.coords = coords    #tuple (x,y)
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
                self.h_rates = [x * 1.33 for x in self.h_rates]
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
        rates = [20, 30, 35, 41, 47, 55, 64, 74, 86, 100, 117,
                 136, 158, 184, 214, 249, 289, 337, 391, 455,
                 530, 616, 717, 833, 969, 1127, 1311, 1525, 1774,
                 2063, 2400]

        return rates

    def __str__(self):
        return "id: {0}, coords: {1}, h_rates: {2}".format(self.id, self.coords, self.h_rates)

    def __repr__(self):
        return self.__str__()