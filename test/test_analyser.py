import pytest
from test_data import package_example
from VPLCodeGenerator.analyser import Variable, _docstr, _cut
from VPLCodeGenerator.inspect_util import empty


def test_docstring_cut():
    assert _cut('docs') == 'docs'
    assert _cut('docs'*6) == 'docs'*5 + '…'


class TestVariables:
    def setup_method(self):
        self.v = Variable('package_example', 'ClassB.attr8', docstring=' This is class attr',
                          annotation=package_example.ClassB.__annotations__['attr8'], default_value='class attr 8',
                          taken_from=['package_example.ClassB', 'attr8'])

    def test_repr(self):
        assert f'{self.v!r}' == f'<var attr8: ClassVar[str] = \'class attr 8\'{_docstr(self.v)}>'

    def test_is_methodvar(self):
        assert self.v.is_classvar
        v = Variable(package_example.ClassB, 'attr3', docstring='',
                     annotation=__builtins__['float'], default_value='3',
                     taken_from=['package_example.ClassB', 'attr3'])
        assert not v.is_classvar

    def test_full_name(self):
        assert self.v.fullname == 'package_example.ClassB.attr8'

    def test_name(self):
        assert self.v.name == 'attr8'

    def test_docstring(self):
        assert self.v.docstring == 'This is class attr'

    def test_type(self):
        assert Variable.type == 'variable'
        assert Variable('', '', docstring='', annotation='', default_value=None, taken_from=None).type == 'variable'

    @pytest.mark.parametrize("actual, expected", [(package_example.ClassB.__annotations__['attr8'], ': ClassVar[str]'),
                                                      (empty, '')])
    def test_annotatiosn_str(self, actual, expected):
        self.v.annotation = actual
        assert self.v.annotation_str == expected

    @pytest.mark.parametrize("actual, expected",
                             [('class attr 8', ' = \'class attr 8\''),
                              (empty, '')])
    def test_default_value_str(self, actual, expected):
        self.v.default_value = actual
        assert self.v.default_value_str == expected

    def test_default_value_exception(self):
        class C:
            def __repr__(self):
                raise Exception
        self.v.default_value = C()
        assert self.v.default_value_str == " = <unable to get value representation>"
