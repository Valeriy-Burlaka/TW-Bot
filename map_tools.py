import re
import shelve
import time
import json
import random
import logging
from math import sqrt


class MapParser:
    """
    Component, responsible for parsing map data from
    a given map_overview file.
    Processes HTML file (as string) and extracts JSON data
    with all sectors/villages from it.
    Manipulates extracted JSON data and structures it to
    bring it to view [sector_data1, sector_data2, ...], where
    sector_data is a dictionary:
    {key=tuple(x_coordinate, y_coordinate): value=[village_data], ..}

    Methods:

    collect_sector_data(overview_html):
        returns structured sectors_data
    """

    def collect_sector_data(self, map_overview_html):
        structured_sectors = []
        raw_sectors_data = self.get_map_data(map_overview_html)
        for sector_data in raw_sectors_data:
            sector = {}
            sector_x = sector_data['x']
            sector_y = sector_data['y']
            sector_villages = sector_data['data']['villages']
            # Some fun below: there are cases, when game stores
            # sector villages in different data types.
            # 1) case: index is x coordinate, value is a dict of villages
            # that lie on a y axis for given x.
            if isinstance(sector_villages, list):
                sector_gen = enumerate(sector_villages)
            # 2) case: key is x coordinate, value is a dict of villages
            # which lie on a y axis for given x.
            elif isinstance(sector_villages, dict):
                sector_gen = sector_villages.items()
            assert sector_gen

            for x, y_axis in sector_gen:
                x = int(x)
                for y, village_data in y_axis.items():
                    villa_x = sector_x + x
                    villa_y = sector_y + int(y)
                    villa_coords = (villa_x, villa_y)
                    sector[villa_coords] = village_data
            structured_sectors.append(sector)

        return structured_sectors

    @staticmethod
    def get_map_data(html_data):
        """
        Looks for string containg sector data (JSON)
        Returns unstructured dict containing sector data
        """
        ptrn = re.compile('TWMap.sectorPrefech = ([\W\w]+?\]);')
        match = re.search(ptrn, html_data)
        js_res = match.group(1)
        res = json.loads(js_res)
        return res




class Map:
    """
    A collecton of barbarian & bonus Villages (neutral).
    Responsible for taking HTML map overview from
    RequestManager and building a mapping of Village objects.
    Responsible for giving a mapping of all villages in a particular range.
    Responsible for storing and updating villages in a local shelve file.
    """

    def __init__(self, base_x, base_y, request_manager,
                 lock, run_path, depth=2, mapfile='map'):
        self.request_manager = request_manager
        self.lock = lock
        self.run_path = run_path
        self.villages = {}  # {(x,y): {'village': Village, 'distance': int}
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
                # Saved village remained Bonus/Barbarian
                if coords in self.villages:
                    # Update with saved data
                    self.villages[coords] = village
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
        event_msg = "Started to build villages from ({x},{y}) base point." \
                    "Map depth={depth}".format(x=x,y=y,depth=depth)
        logging.info(event_msg)
        map_html = self.get_map_overview(x, y)
        # list of dicts, each dict represents 1 sector


            if depth:
                sector_corners = self.get_sector_corners(sector_coords)
                event_msg = "Calculated the next sector " \
                            "corners: {}".format(sector_corners)
                logging.info(event_msg)
                for corner in sector_corners:
                    time.sleep(random.random() * 6)
                    self.build_villages(*corner, depth=depth)

        logging.info("Villages upon map init: {}".format(self.villages))

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
        """
        Constructs a Village obj from given data
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



    def get_targets_in_radius(self, radius, source_coords):
        targets = []
        for coords, villa in self.villages.items():
            distance = self.calculate_distance(source_coords, coords)
            if distance <= radius: targets.append((coords, distance))

        return targets
