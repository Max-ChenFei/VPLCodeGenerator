import os
import pickle

import numpy
from sphinx.application import ENV_PICKLE_FILENAME

from VPLCodeGenerator.analyser import Module, Class, Function, Variable
from VPLCodeGenerator.parser import ReSTParser, ReSTParserSuit


def get_test_parse_suit():
    test_dir = os.path.dirname(os.path.dirname(__file__))
    test_data_dir = os.path.join(test_dir, r'test_data\reST')
    env = None
    with open(os.path.join(test_data_dir, ENV_PICKLE_FILENAME), 'rb') as f:
        env = pickle.load(f)
        if env is None:
            raise Exception('Sphinx Environment is None.')
    doctree = {'index': 'reference/index',
               'reference/index': ['reference/arrays', 'reference/constants', 'reference/routines'],
               'reference/arrays': ['reference/arrays.ndarray', 'reference/generated/numpy.ndarray.flags'],
               'reference/arrays.ndarray': ['reference/generated/numpy.ndarray'],
               'reference/generated/numpy.ndarray': ['reference/generated/numpy.ndarray.all'],
               'reference/routines': ['reference/routines.array-creation'],
               'reference/routines.array-creation': ['reference/generated/numpy.empty'],
               }
    env.toctree_includes = doctree
    env.doctreedir = os.path.join(test_data_dir, r'.doctree')
    return ReSTParserSuit(env)


class TestReSTParserSuit:
    parser_suit = None

    def setup_method(self):
        self.parser_suit = get_test_parse_suit()

    def test_parser_types(self):
        assert self.parser_suit['default'] == ReSTParser

    def test_name(self):
        assert self.parser_suit.name() == 'reST'

    def test_doctreedir(self):
        assert self.parser_suit.doctreedir == self.parser_suit.env.doctreedir

    def test_toctree(self):
        assert self.parser_suit.toctree('index')


def create_module(reST_path, parser_suit):
    parser = parser_suit['module'](reST_path, parser_suit)
    title = parser_suit.find_title(reST_path)
    return Module('', title, None, (), parser)


class TestReSTParser:
    parser_suit = None
    parser = None

    def setup_method(self):
        self.parser_suit = get_test_parse_suit()

    def test_members_of_index(self):
        self.parser = self.parser_suit['module']('reference/index', self.parser_suit)
        assert self.parser.members() == {}

    def test_empty_members(self):
        self.parser = self.parser_suit['module']('reference/arrays', self.parser_suit)
        assert self.parser.members() == {}

    def test_class_members(self):
        self.parser = self.parser_suit['module']('reference/generated/numpy.ndarray', self.parser_suit)
        expected = self.parser.members()
        actual = Class('numpy', 'ndarray', numpy.ndarray, ('numpy', 'ndarray'))
        assert expected['numpy.ndarray'] == actual

    def test_method_members(self):
        self.parser = self.parser_suit['module']('reference/generated/numpy.ndarray.all', self.parser_suit)
        expected = self.parser.members()
        actual = Function('numpy', 'ndarray.all', numpy.ndarray.all, ('numpy', 'ndarray.all'))
        assert expected['numpy.ndarray.all'] == actual

    def test_attribute_members(self):
        self.parser = self.parser_suit['module']('reference/generated/numpy.ndarray.flags', self.parser_suit)
        expected = self.parser.members()
        actual = Variable('numpy', 'ndarray.flags', taken_from=('numpy', 'ndarray.flags'),
                          docstring='', default_value=numpy.ndarray.flags, is_const=False)
        assert expected['numpy.ndarray.flags'] == actual

    def test_data_members(self):
        self.parser = self.parser_suit['module']('reference/constants', self.parser_suit)
        expected = self.parser.members()
        actual = {"numpy.Inf": Variable('numpy', 'Inf', taken_from=('numpy', 'Inf'),
                                        docstring='', default_value=numpy.Inf, is_const=True),
                  "numpy.pi": Variable('numpy', 'pi', taken_from=('numpy', 'pi'),
                                       docstring='', default_value=numpy.pi, is_const=True)}
        assert len(expected) == 15
        for key in actual.keys():
            expected[key] == actual[key]

    def test_func_members(self):
        self.parser = self.parser_suit['module']('reference/generated/numpy.empty', self.parser_suit)
        expected = self.parser.members()
        actual = Function('numpy', 'empty', numpy.empty, ('numpy', 'empty'))
        assert expected['numpy.empty'] == actual

    def test_submodules(self):
        self.parser = self.parser_suit['module']('reference/index', self.parser_suit)
        actual = self.parser.submodules()
        expect = []
        for path in ['reference/arrays', 'reference/constants', 'reference/routines']:
            expect.append(create_module(path, self.parser_suit))
        assert actual == expect
