import re
import shelve
import json
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
            # 1) case: 'sector_villages' is a list, where indices are
            # x coordinates, items on these indices are dicts of villages
            # that lie on a y axis for this x.
            if isinstance(sector_villages, list):
                sector_gen = enumerate(sector_villages)
            # 2) case: 'sector_villages' is a dict, where keys are x
            # coordinates, values are dicts of villages
            # that lie on a y axis for given x.
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


class MapMath:
    """
    Provides helper methods for operations with villages on map.

    Methods:

    calculate_distance:
        takes source and target coordinates
        returns rounded distance between them

    get_area_corners:
        takes a sequence of coordinates and tries to find
        4 most outer coordinates in this sequence.
        return list of tuples(x,y)

    get_targets_in_radius:
        tries to determine which target villages lie in a given
        radius from source (attacking) village.
        returns list of tuples:
        [((target_x_coordinate, target_y_coordinate), distance_to_target), ...]
    """

    @classmethod
    def calculate_distance(cls, source_coords, target_coords):
        x = target_coords[0]
        y = target_coords[1]
        side_x = abs(source_coords[0] - x)
        side_y = abs(source_coords[1] - y)
        distance = sqrt(side_x**2 + side_y**2)
        return round(distance, 2)

    @staticmethod
    def get_area_corners(area_coords):
        """
        Roughly determines area's corner points.
        Returns list of 4 points ( [(x_min, y_min), (x_max, y_max), ....])
        """
        area_coords = sorted(area_coords)
        min_x_min_y = area_coords[0]
        max_x_max_y = area_coords[-1]
        # Sort area coords by Y coordinate and in reversed order.
        # Thus, 1st item in resulting sequence is a point with
        # minimum X & maximum Y, last item = maximum X & minimum Y
        area_coords = sorted(area_coords, key=lambda item: item[1], reverse=True)
        # Retrieve remaining corner points that are distinct from MIN_MIN
        # and MAX_MAX points (we can have only one village on the outermost axis,
        # so, for example, MIN_MIN point will be equal to MIN_MAX point.
        for point in area_coords:
            if point != min_x_min_y:
                min_x_max_y = point
                break
        for point in reversed(area_coords):
            if point != max_x_max_y:
                max_x_min_y = point
                break
        try:
            corners = [min_x_min_y, max_x_max_y, min_x_max_y, max_x_min_y]
        # Impossible situation (2 villages in area at all), however..
        except NameError:
            corners = [min_x_min_y, max_x_max_y, min_x_min_y, max_x_max_y]

        return corners

    @staticmethod
    def get_targets_in_radius(source_coords, radius, villages):
        targets = []
        for coords, villa in villages.items():
            distance = MapMath.calculate_distance(source_coords, coords)
            if distance <= radius:
                targets.append((coords, distance))

        return targets


class MapStorage:
    """
    Delegates save & update operations to one of storage-helpers
    """

    def __init__(self, storage_type, storage_name):
        if storage_type == 'local_file':
            self.storage_processor = LocalStorage(storage_name)
        else:
            raise NotImplementedError("Specified storage type for map data"
                                      "is not implemented yet!")

    def get_saved_villages(self):
        saved_villages = self.storage_processor.get_saved_villages()
        return saved_villages

    def update_villages(self, villages):
        self.storage_processor.update_villages(villages)


class LocalStorage:
    """
    Handles retrieval & update of village data saved in a local file.

    Methods:

    get_saved_villages:
        returns villages that were saved in a local shelve file

    update_villages:
        updates information about (attacked) villages in a local
        shelve file
    """

    def __init__(self, storage_name):
        self.storage_name = storage_name

    def get_saved_villages(self):
        storage = shelve.open(self.storage_name)
        saved_villages = storage.get('villages', {})
        storage.close()
        return saved_villages

    def update_villages(self, villages):
        storage = shelve.open(self.storage_name)
        if 'villages' in storage:
            saved_villages = storage['villages']
        else:
            saved_villages = {}
        for coords, village in villages.items():
            saved_villages[coords] = village

        storage['villages'] = saved_villages
        storage.close()

