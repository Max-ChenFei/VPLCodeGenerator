import pytest
from inspect import getsource
from test_data import package_example
from VPLCodeGenerator.parser import obj_type, VariableParser, SourceCodeParser


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
