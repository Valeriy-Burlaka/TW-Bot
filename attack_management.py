__author__ = 'Troll'

import time
from map_management import Map

class AttackQueue:
    """
    Keeps queue of villages basing on distance to them
    and on remaining/estimated amount of resources to loot.
    Answers which village can be attacked next
    with current amount of troops.
    Updates villages with new AttackReports.
    Updates Map with villages.
    """

    def __init__(self, x, y, request_manager, map_depth=2, mapfile='map', queue_depth=5,
                 farm_frequency=3, farm_radius=24, capacity_threshold=1600, initial_capacity=2400):
        self.map = Map(x, y, request_manager, depth=map_depth, mapfile=mapfile)
        self.depth = queue_depth    # Number of next priorities
        self.rest = farm_frequency*3600 # How long villages rest between attacks in seconds
        self.radius = farm_radius   # Radius from player's village in tiles
        self.threshold = capacity_threshold # To not send very few troops in attack
        self.initial_capacity = initial_capacity    # Expected capacity in villages that were not attacked yet
        self.villages = self.map.get_villages_in_range(self.radius)
        self.queue = []
        self.build_queue()

    def build_queue(self):
        """Builds queue from villages that are ready for farm
        and sorts it ascending by distance (nearest=first)"""
        # v_data = {'village': Village, 'distance':distance]
        queue = [villa for villa in self.villages.values() if self.is_ready_for_farm(villa)]
        # assign queue sorted by distance
        self.queue = sorted(queue, key=lambda x: x.dist_from_base)

    def is_ready_for_farm(self, village):
        return village.passes_threshold(self.threshold) or village.is_fresh_meat() or village.finished_rest(self.rest)

    def estimate_arrival(self, distance, speed):
        """Returns time of arrival (GMT) basing on
        given distance and speed. Speed is a unit.speed value
        and means minutes-per-tile value
        """
        time_on_road = distance*speed*60    # e.g.: 6 tiles * 10 minutes-per-tile * seconds
        time_gmt = time.mktime(time.gmtime())
        estimated_arrival = round(time_gmt + time_on_road)
        return estimated_arrival

    def estimate_troops_needed(self, unit, estimated_capacity=None):
        if not estimated_capacity: estimated_capacity = self.initial_capacity
        return round(estimated_capacity/unit.haul)

    def is_attack_possible(self, villa, troops_map):
        """Evaluates if there enough troops to loot all
        village resources at the time of arrival with current troops.
        Returns dict {Unit_obj: number to send}
        """
        for unit, count in troops_map.items():
            if villa.is_fresh_meat():   # No info about last_visited & remaining_capacity
                units_needed = self.estimate_troops_needed(unit)
            else:
                speed = unit.speed
                t_of_arrival = self.estimate_arrival(villa.dist_from_base, speed)
                estimated_capacity = villa.estimate_capacity(t_of_arrival)
                units_needed = self.estimate_troops_needed(unit, estimated_capacity)
            if units_needed <= count:
                return {unit: units_needed}

        else: return

    def get_next_attack_target(self, troops_map):
        """Decides if nearest villages in self.queue could
         be attacked with existing amount of troops.
         Number of checked villages is based on self.depth.
         If it's possible to attack, returns coordinates and
         amount of troops, otherwise - None
         """
        if self.queue:  # there is something to farm
            high_priority = self.queue[0]
            check = self.is_attack_possible(high_priority, troops_map)
            if check:
                self.queue.remove(high_priority)
                return (high_priority.coords, check)
            else:
                next_priorities = self.queue[1:self.depth+1]
                if next_priorities:
                    for villa in next_priorities:
                        check = self.is_attack_possible(villa, troops_map)
                        if check:
                            self.queue.remove(villa)
                            return (villa.coords, check)

        return

    def update_villages(self, new_reports):
        """Updates self.villages with a new reports
        """
        for coords, report in new_reports.items():
            print(coords)
            print(report)
            print(self.villages[coords])
            self.villages[coords].update_stats(report)
        self.map.update_villages(self.villages)
        # Re-build self.queue basing on last information
        self.build_queue()


class Unit:
    """Simple representation of TW unit.
    Should define attributes in sub-classes
    """

    def __str__(self):
        return "Unit: {0}, speed: {1}, haul: {2}".format(self.name, self.speed, self.haul)

    def __repr__(self):
        return self.__str__()

class LightCavalry(Unit):

    def __init__(self):
        self.name = 'LightCavalry'
        self.speed = 10
        self.haul  = 80

class Axeman(Unit):

    def __init__(self):
        self.name = 'Axe'
        self.speed = 18
        self.haul  = 10
