from unittest import mock

import factory
from factory.fuzzy import FuzzyInteger, FuzzyText

from bot.libs.village_management import TargetVillage
from bot.libs.village_management import PlayerVillage


@factory.use_strategy(factory.BUILD_STRATEGY)
class TargetVillageFactory(factory.Factory):
    FACTORY_FOR = TargetVillage

    @factory.lazy_attribute
    def coords(self):
        return (FuzzyInteger(1, 999).fuzz(), FuzzyInteger(1, 999).fuzz())

    @factory.lazy_attribute
    def id_(self):
        return FuzzyInteger(1, 10000).fuzz()

    @factory.lazy_attribute
    def population(self):
        return FuzzyInteger(1,1000).fuzz()

    @factory.lazy_attribute
    def bonus(self):
        return None


@factory.use_strategy(factory.BUILD_STRATEGY)
class PlayerVillageFactory(factory.Factory):
    FACTORY_FOR = PlayerVillage

    @factory.lazy_attribute
    def coords(self):
        return FuzzyInteger(1, 999).fuzz(), FuzzyInteger(1, 999).fuzz()

    @factory.lazy_attribute
    def id_(self):
        return FuzzyInteger(1, 10000).fuzz()

    @factory.lazy_attribute
    def name(self):
        return FuzzyText(prefix="Village ").fuzz()


