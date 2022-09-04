from VPLCodeGenerator.parser import ParserSuitsRegistry, ReSTParserSuit, SourceCodeParserSuit


class TestParserSuitsRegistry:
    def setup_method(self):
        self.registry = ParserSuitsRegistry()

    def test_available_parser_suit_types(self):
        actual = self.registry.available_parser_suit_types()
        assert actual == [SourceCodeParserSuit.name(), ReSTParserSuit.name()]

    def test_get(self):
        actual = self.registry[SourceCodeParserSuit.name()]
        assert actual == SourceCodeParserSuit
        actual = self.registry[ReSTParserSuit.name()]
        assert actual == ReSTParserSuit
