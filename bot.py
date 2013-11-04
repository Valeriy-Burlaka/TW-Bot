"""
This module was created to automate farming
process in browser strategy game TribalWars.
See "TribalWars Super.docx" design document for details.
"""

import time
import re


class AttackReport:
    """
    Extracts valuable data from a HTML string for
    a particular attack report.
    Neither xml.etree.ElementTree nor xml.dom.minidom
    in-build DOM parsers were able to parse TribalWars 
    attack reports, so using regular expressions instead.
    """
    
    def __init__(self, str_html):
        self.data = str_html
        self.build_report()
    
    def build_report(self):
        self.set_status()
        self.set_t_of_attack()
        self.set_mines_level()
        self.set_capacities()
    
    def set_status(self):
        match = re.search(r'/graphic/dots/(\w+).png', self.data)    # green, yellow or red
        self.status = match.group(1)
    
    def set_t_of_attack(self):        
        months = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, 
                  "Jun":6, "Jul":7, "Aug":8, "Sep":9, "Oct":10,
                  "Nov":11, "Dec":12}
                  
        # "Nov 03, 2013  14:01:57" 
        pattern = re.compile(r'(\w{3})\s(\d\d),\s(\d{4})\s\s(\d\d):(\d\d):(\d\d)')
        match = re.search(pattern, self.data)
        month = months[match.group(1)]
        day = int(match.group(2))
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        second = int(match.group(6))
        
        struct_t = time.struct_time(
                   (year, month, day, hour, minute, second, 0, 0, 0))
        self.t_of_attack = round(time.mktime(struct_t))
    
    def set_mines_level(self):
        mines = ["Timber camp", "Clay pit", "Iron mine"]
        levels = []
        for mine in mines:
            search = r'{}\s<b>\WLevel\s(\d)\W</b>'.format(mine) # "Barracks <b>(Level 4)</b>"
            match = re.search(search, self.data)
            levels.append(int(match.group(1)))
        self.mine_levels = levels
    
    def set_capacities(self):         
        scouted = re.search(r'Resources scouted:[\w\W]+Buildings:', self.data).group()
        looted = re.search(r'Haul:[\w\W]+Publicize this report', self.data).group()
        
        def get_haul_amount(s_resources):
            # <span class="icon header stone"> </span>800 
            wood_pattern = re.compile(r'"icon header wood"> </span>(\d+)')
            clay_pattern = re.compile(r'"icon header stone"> </span>(\d+)')
            iron_pattern = re.compile(r'"icon header iron"> </span>(\d+)')
            i_amount = 0
            for ptrn in (wood_pattern, clay_pattern, iron_pattern,):
                match = re.search(ptrn, s_resources)
                s_resource = match.group()
                # floats look like "...wood"> </span>1 span class="grey">.</span>175"
                amounts = re.findall(r'\d+', s_resource)
                for s in amounts:
                    i_amount += int(s)            
            return i_amount
        
        self.remaining_capacity = get_haul_amount(scouted)
        self.looted_capacity = get_haul_amount(looted)       

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
        
        