import pytest
from inspect import getsource
from importlib import import_module
from test_data import package_example
from VPLCodeGenerator.parser import obj_type, VariableParser, SourceCodeParser, SourceCodeModuleParser


def test_obj_type():
    assert obj_type(package_example) == 'module'
    assert obj_type(package_example.subpackage.SubmoduleC) == 'class'


@pytest.mark.parametrize("test_input, expected", [(package_example.name,
                                                   f'This type ({type(package_example.name)}) '
                                                   f'of object is not supported'),
                                                  (package_example.subpackage.SubmoduleC.myname,
                                                   f'This type ({type(package_example.subpackage.SubmoduleC.myname)})'
                                                   f' of object is not supported')])
def test_obj_type_exception(test_input, expected):
    with pytest.raises(TypeError) as excinfo:
        obj_type(test_input)
        assert str(excinfo.value) == expected


class TestSourceCodeParser:
    encoding = 'utf-8'
    obj = package_example
    code = getsource(obj)

    def setup_method(self):
        self.parser = SourceCodeParser(self.obj, self.encoding)

    def test_attribute_assignment_in_init(self):
        assert self.parser.obj == self.obj
        assert self.parser.type == obj_type(self.obj)
        assert self.parser.code == self.code
        assert self.parser.namespace == ''
        assert self.parser._variable_parser == VariableParser(self.code, self.encoding)

    def test_return_empty_list_when_not_package(self):
        self.parser = SourceCodeParser(self.obj.ClassA, self.encoding)
        assert self.parser.submodules == []

    def test_vars_sets(self, mocker):
        var_docstr = {'var1': 'doc1', 'var2': 'doc1'}
        var_annots = {'var1': 'doc1', 'var3': 'doc1'}
        mocker.patch.object(self.parser, 'var_docstring', var_docstr)
        mocker.patch.object(self.parser, 'var_annotations', var_annots)
        assert self.parser.vars_sets == var_docstr.keys() | var_annots.keys()


class TestSourceCodeModuleParser(TestSourceCodeParser):
    def setup_method(self):
        self.parser = SourceCodeModuleParser(self.obj, self.encoding)

    def test_var_docstring(self):
        expected: dict[str, str] = VariableParser(self.code, self.encoding).docstring_in_ns(self.parser.namespace)
        if expected is None or expected == {}:
            raise Exception('No var docstring found, please use other test data')
        assert self.parser.var_docstring == expected

    def test_var_annotations(self):
        expected: dict[str, str] = VariableParser(self.code, self.encoding).annotations_in_ns(self.parser.namespace)
        if expected is None or expected == {}:
            raise Exception('No var annotations found, please use other test data')
        assert self.parser.var_annotations == expected

    def test_member_objects(self):
        assert True

    def test_submodules_when_have_all_attr(self):
        expected_modules = [package_example.submodule_b]
        for actual, expected in zip(self.parser.submodules, expected_modules):
            assert actual == expected

    def test_submodules_when_no_all_attr(self):
        all_attr = self.obj.__all__
        del self.obj.__all__
        parser = SourceCodeModuleParser(self.obj, self.encoding)
        expected_modules = [package_example.submodule_b, package_example.subpackage]
        for actual, expected in zip(parser.submodules, expected_modules):
            assert actual == expected
        self.obj.__all__ = all_attr

    def test_submodules_return_empty(self):
        self.parser = SourceCodeModuleParser(self.obj.submodule_a, self.encoding)
        assert self.parser.submodules == []

    def test_member_objects_when_have_all_attr(self):
        attrs = self.obj.__dict__
        import numpy
        expected = [attrs['submodule_a'], attrs['submodule_b'], attrs['ClassA'], attrs['SubmoduleC'],
                    numpy, attrs['module_level_function'], attrs['var1'], empty, attrs['instance_of_a']]
        for n, v, actual in zip(self.obj.__all__, expected, self.parser.member_objects.items()):
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
                            'test_data.package_example.submodule_b': import_module('test_data.package_example.submodule_b'),
                            'test_data.package_example.subpackage': import_module('test_data.package_example.subpackage')}
        for actual, expected in zip(parser.member_objects, expected_members):
            assert actual == expected

        self.obj.__all__ = all_attr
