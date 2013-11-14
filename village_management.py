__author__ = 'Troll'

import re

class VillageStateManager():
    """
    Component responsible for getting and keeping information
    about player's village (troops, resources).
    Future improvements: subclass from Thread,
    extend for tracking building/hire queues, incoming attacks,
    making decisions about resources usage.
    """

    def __init__(self, request_manager, lock, village_id):
        self.request_manager = request_manager
        self.lock = lock
        self.id = village_id
        self.units_names = self.get_units_names()

    def get_troops_map(self, battle_units):
        self.lock.acquire()
        overview_html = self.request_manager.get_village_overview(self.id)
        self.lock.release()
        if overview_html:
            troops_map = self.form_troops_map(overview_html, battle_units)
            return troops_map

    def form_troops_map(self, html_data, battle_units):
        """
        Parses given village-overview html to get troops count.
        Inits Units from self.units_data, returns mapping
        {Unit: count, ...
        """
        troops_map = {}
        units_in_village = re.findall(r'<strong>(\d+)</strong>\W*?(\w+\s*\w*)', html_data)
        if units_in_village:
            for count, unit_ingame_name in units_in_village:
                unit_ingame_name = unit_ingame_name.rstrip()
                if unit_ingame_name in battle_units:
                    unit_name = self.units_names[unit_ingame_name]
                    count = int(count)
                    troops_map[unit_name] = count

        return troops_map

    def get_units_names(self):
        """
        Returns mapping {'game_name':[name, speed, haul],..}, where
        'game_name' is unit name as it appears in village_overview
        html page, value is a list with unit stats needed to init Unit obj.
        """

        units_data = {'Axemen': 'axe', 'Scouts': 'spy',
                      'Light cavalry': 'light', 'Heavy cavalry': 'heavy'}
        return units_data