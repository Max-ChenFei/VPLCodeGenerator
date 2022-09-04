from abc import ABC, abstractmethod


class ParserSuitsRegistry:
    def __init__(self):
        self.suits = {}
        for cls in ParserSuit.__subclasses__():
            self.register_parser_suit_type(cls.name(), cls)

    def register_parser_suit_type(self, name, obj):
        self.suits.setdefault(name, obj)

    def __getitem__(self, name):
        if name in self.suits.keys():
            return self.suits[name]
        raise Exception(f'{name} do not support.')

    def available_parser_suit_types(self):
        return list(self.suits.keys())


class ParserSuit(ABC):
    parser_types = {'default': None}

    @staticmethod
    def name():
        NotImplementedError

    def __getitem__(self, item):
        try:
            return self.parser_types[item]
        except:
            return self.parser_types['default']


class Parser(ABC):
    @abstractmethod
    def members(self):
        NotImplementedError

    def submodules(self):
        return []
