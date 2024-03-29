import pytest
from inspect import getsource, cleandoc
from importlib import import_module
from test_data import package_example
from VPLCodeGenerator.parser import (VariableParser, SourceCodeParser,
                                     SourceCodeModuleParser, SourceCodeClassParser, resolve_annotations)
from VPLCodeGenerator.inspect_util import empty


class TestSourceCodeParser:
    encoding = 'utf-8'
    obj = package_example
    code = getsource(obj)

    def setup_method(self):
        self.parser = SourceCodeParser(self.obj, self.encoding)

    def test_attribute_assignment_in_init(self):
        assert self.parser.obj == self.obj
        assert self.parser.namespace == ''
        assert self.parser._variable_parser == VariableParser(self.code, self.encoding)

    def test_vars_sets(self, mocker):
        var_docstr = {'var1': 'doc1', 'var2': 'doc1'}
        var_annots = {'var1': 'doc1', 'var3': 'doc1'}
        mocker.patch(f'{SourceCodeParser.__module__}.{SourceCodeParser.__name__}.var_docstring',
                     new_callable=mocker.PropertyMock, return_value=var_docstr)
        mocker.patch(f'{SourceCodeParser.__module__}.{SourceCodeParser.__name__}.var_annotations',
                     new_callable=mocker.PropertyMock, return_value=var_annots)
        self.parser = SourceCodeParser(self.obj, self.encoding)
        assert self.parser.vars_sets() == var_docstr.keys() | var_annots.keys()


class TestSourceCodeModuleParser(TestSourceCodeParser):
    def setup_method(self):
        self.parser = SourceCodeModuleParser(self.obj, self.encoding)

    def test_var_docstring(self):
        expected: dict[str, str] = VariableParser(self.code, self.encoding).docstring_in_ns(self.parser.namespace)
        if expected is None or expected == {}:
            raise Exception('No var docstring found, please use other test data')
        assert self.parser.var_docstring == expected

    def test_var_annotations(self):
        annotations: dict[str, str] = VariableParser(self.code, self.encoding).annotations_in_ns(self.parser.namespace)
        expected = resolve_annotations(self.obj, annotations, self.obj.__name__)
        if expected is None or expected == {}:
            raise Exception('No var annotations found, please use other test data')
        assert self.parser.var_annotations == expected

    def test_submodules_when_have_all_attr(self):
        expected_modules = [package_example.submodule_b]
        for actual, expected in zip(self.parser.submodules(), expected_modules):
            assert actual == expected

    def test_submodules_when_no_all_attr(self):
        all_attr = self.obj.__all__
        del self.obj.__all__
        parser = SourceCodeModuleParser(self.obj, self.encoding)
        expected_modules = [package_example.submodule_b, package_example.subpackage]
        for actual, expected in zip(parser.submodules(), expected_modules):
            assert actual == expected
        self.obj.__all__ = all_attr

    def test_submodules_return_empty(self):
        self.parser = SourceCodeModuleParser(self.obj.submodule_a, self.encoding)
        assert self.parser.submodules() == []

    def test_member_objects_when_have_all_attr(self):
        attrs = self.obj.__dict__
        import numpy
        expected = [attrs['submodule_a'], attrs['submodule_b'], attrs['ClassA'], attrs['SubmoduleC'],
                    numpy, attrs['module_level_function'], attrs['var1'], empty, attrs['instance_of_a']]
        for n, v, actual in zip(self.obj.__all__, expected, self.parser.member_objects().items()):
            assert actual[0] == n
            assert actual[1] == v

    def test_member_objects_when_no_all_attr(self):
        all_attr = self.obj.__all__
        del self.obj.__all__
        parser = SourceCodeModuleParser(self.obj, self.encoding)
        attrs = self.obj.__dict__
        expected_members = {'module_level_function': attrs['submodule_a'], 'ClassA': attrs['ClassA'],
                            'instance_of_a': attrs['instance_of_a'], 'var1': attrs['var1'],
                            'var3': attrs['var3'], 'var4': attrs['var4'], 'var5': attrs['var5'],
                            'ClassB': attrs['ClassB'], 'instance_of_b': attrs['instance_of_b'],
                            'test_data.package_example.submodule_b':
                                import_module('test_data.package_example.submodule_b'),
                            'test_data.package_example.subpackage':
                                import_module('test_data.package_example.subpackage')}
        for actual, expected in zip(parser.member_objects(), expected_members):
            assert actual == expected

        self.obj.__all__ = all_attr


class TestSourceCodeClassParser:
    encoding = 'utf-8'
    obj = package_example.ClassB
    code = getsource(obj)

    def setup_method(self):
        self.parser = SourceCodeClassParser(self.obj, self.encoding)

    def test_attribute_assignment_in_init(self):
        assert self.parser.obj == self.obj
        assert self.parser.namespace == self.obj.__name__

    def test_var_docstring(self):
        obj = package_example.ClassA
        p = VariableParser(getsource(obj), self.encoding)
        expected: dict[str, str] = p.docstring_in_ns(obj.__name__)
        expected['attr8'] = 'This is class attr'
        if expected is None or expected == {}:
            raise Exception('No var docstring found, please use other test data')
        assert self.parser.var_docstring == expected

    def test_var_annotations(self):
        obj = package_example.ClassA
        p = VariableParser(getsource(obj), self.encoding)
        annotations: dict[str, str] = p.annotations_in_ns(obj.__name__)
        expected = resolve_annotations(self.obj, annotations, self.obj.__name__)
        if expected is None or expected == {}:
            raise Exception('No var annotations found, please use other test data')
        assert self.parser.var_annotations == expected

    def test_member_objects(self):
        actual = self.parser.member_objects()
        expected = {'__init__': package_example.ClassA.__init__, '__module__': self.obj.__module__,
                    '__doc__': cleandoc(self.obj.__doc__), '__annotations__': self.obj.__annotations__,
                    '__dict__': self.obj.__dict__, '__weakref__': self.obj.__weakref__,
                    'staticmethod': self.obj.__dict__['staticmethod'],
                    'classmethod': self.obj.__dict__['classmethod'],
                    'classmethodinA': package_example.ClassA.__dict__['classmethodinA'],
                    'async_fun': package_example.ClassB.__dict__['async_fun'],
                    'init_attr7': self.obj.init_attr7, 'get_attr6': self.obj.get_attr6,
                    'update_attr3': self.obj.update_attr3, 'ClassC': self.obj.ClassC,
                    'attr0': empty, 'attr1': 'attr1_v', 'attr2': empty, 'attr3': empty,
                    'attr4': empty, 'attr5': empty, 'attr8': self.obj.attr8
                    }
        assert actual.keys() == expected.keys()
        assert actual == expected

    def test_definitions(self):
        actual = self.parser.definitions
        expected = {'attr0': ('test_data.package_example', 'ClassA.attr0'),
                    'attr1': ('test_data.package_example', 'ClassA.attr1'),
                    'attr2': ('test_data.package_example', 'ClassA.attr2'),
                    'attr3': ('test_data.package_example', 'ClassA.attr3'),
                    'attr4': ('test_data.package_example', 'ClassA.attr4'),
                    'attr5': ('test_data.package_example', 'ClassA.attr5'),
                    'update_attr3': ('test_data.package_example', 'ClassA.update_attr3'),
                    'classmethodinA': ('test_data.package_example', 'ClassA.classmethodinA'),
                    '__weakref__': ('test_data.package_example', 'ClassA.__weakref__'),
                    'ClassC': ('test_data.package_example', 'ClassA.ClassC'),
                    'attr8': ('test_data.package_example', 'ClassB.attr8'),
                    '__init__': ('test_data.package_example', 'ClassB.__init__'),
                    '__module__': ('test_data.package_example', 'ClassB.__module__'),
                    '__annotations__': ('test_data.package_example', 'ClassB.__annotations__'),
                    '__doc__': ('test_data.package_example', 'ClassB.__doc__'),
                    'staticmethod': ('test_data.package_example', 'ClassB.staticmethod'),
                    'classmethod': ('test_data.package_example', 'ClassB.classmethod'),
                    'init_attr7': ('test_data.package_example', 'ClassB.init_attr7'),
                    'get_attr6': ('test_data.package_example', 'ClassA.get_attr6'),
                    'async_fun': ('test_data.package_example', 'ClassB.async_fun'),
                    '__dict__': ('test_data.package_example', 'ClassB.__dict__')}
        assert actual == expected
