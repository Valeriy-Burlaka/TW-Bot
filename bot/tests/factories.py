import factory
from factory.fuzzy import FuzzyInteger

from bot.libs.village_management import TargetVillage


class TargetVillageFactory(factory.Factory):
    FACTORY_FOR = TargetVillage

    coords = (FuzzyInteger(1, 999), FuzzyInteger(1, 999))
    id_ = FuzzyInteger(1, 10000)
    population = FuzzyInteger(1, 1000)
    bonus = None