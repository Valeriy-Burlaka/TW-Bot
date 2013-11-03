"""
This module was created to automate farming
process in browser strategy game TribalWars.
See "TribalWars Super.docx" design document for details.
"""

import time


class Village:
    """Represents a single village.
    'Lives' in Map.
    """
    
    def __init__(self, coords, id, bonus=None):
        self.id = id
        self.coords = coords    #tuple (x,y)
        self.bonus = bonus  # str
        self.mine_levels = None #list [wood, clay, iron], integers
        self.h_rates = None
        self.last_visited = None
        self.remaining_capacity = None
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
        else:   # if no info about last_visit, count from now
            t_to_arrival = t_of_arrival - time.mktime(time.localtime())
        
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
        
        