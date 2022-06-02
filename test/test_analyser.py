import inspect
import pytest
from test_data import package_example
# noinspection PyProtectedMember
from VPLCodeGenerator.analyser import Variable, Function, _docstr, _cut, _PrettySignature
from VPLCodeGenerator.inspect_util import empty


def test_docstring_cut():
    assert _cut('docs') == 'docs'
    assert _cut('docs' * 6) == 'docs' * 5 + '…'


class TestVariables:
    def setup_method(self):
        self.v = Variable('package_example', 'ClassB.attr8', docstring=' This is class attr',
                          annotation=package_example.ClassB.__annotations__['attr8'], default_value='class attr 8',
                          taken_from=('package_example.ClassB', 'attr8'))

    def test_repr(self):
        assert f'{self.v!r}' == f'<var attr8: ClassVar[str] = \'class attr 8\'{_docstr(self.v)}>'

    def test_is_methodvar(self):
        assert self.v.is_classvar
        # noinspection PyUnresolvedReferences
        v = Variable(package_example.ClassB.__name__, 'attr3', docstring='',
                     annotation=__builtins__['float'], default_value='3',
                     taken_from=('package_example.ClassB', 'attr3'))
        assert not v.is_classvar

    def test_full_name(self):
        assert self.v.fullname == 'package_example.ClassB.attr8'

    def test_name(self):
        assert self.v.name == 'attr8'

    def test_docstring(self):
        assert self.v.docstring == 'This is class attr'

    def test_type(self):
        assert Variable.type == 'variable'
        assert Variable('', '', docstring='', annotation='', default_value=None,
                        taken_from=('', '')).type == 'variable'

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


def new_function_in(name, in_class='ClassB', taken_from_class='ClassB'):
    modulename = 'package_example'
    qualname = f'{in_class}.{name}'
    obj = getattr(package_example, taken_from_class).__dict__[name]
    return Function(modulename, qualname, obj, (modulename, f'{taken_from_class}.{name}'))


class TestFunction:

    @pytest.mark.parametrize("name, func, taken_from", [('staticmethod',
                                                         package_example.ClassB.__dict__['staticmethod'], 'ClassB'),
                                                        ('classmethod',
                                                         package_example.ClassB.__dict__['classmethod'], 'ClassB'),
                                                        ('update_attr3',
                                                         package_example.ClassA.__dict__['update_attr3'], 'ClassA')])
    def test_function_attributes(self, name, func, taken_from):
        f = new_function_in(name, taken_from, taken_from)
        assert f.wrapped == func
        if isinstance(func, (classmethod, staticmethod)):
            func = func.__func__
        assert f.obj == func
        assert f.parser_config is None
        assert f.taken_from == ('package_example', f'{taken_from}.{name}')

    def test_full_name(self):
        name = 'staticmethod'
        f = new_function_in(name)
        assert f.fullname == f'{f.modulename}.{f.qualname}'

    def test_name(self):
        name = 'staticmethod'
        f = new_function_in(name)
        assert f.name == name

    @pytest.mark.parametrize("name, taken_from, is_classmethod", [('staticmethod', 'ClassB', False),
                                                                  ('classmethod', 'ClassB', True),
                                                                  ('update_attr3', 'ClassA', False)])
    def test_is_classmethod(self, name, taken_from, is_classmethod):
        f = new_function_in(name, taken_from, taken_from)
        assert f.is_classmethod == is_classmethod

    @pytest.mark.parametrize("name, taken_from, is_staticmethod", [('staticmethod', 'ClassB', True),
                                                                   ('classmethod', 'ClassB', False),
                                                                   ('update_attr3', 'ClassA', False)])
    def test_is_staticmethod(self, name, taken_from, is_staticmethod):
        f = new_function_in(name, taken_from, taken_from)
        assert f.is_staticmethod == is_staticmethod

    def test_docstring(self):
        name = 'get_attr6'
        f = new_function_in(name)
        assert f.docstring == 'function docstring, Overrides version from class A'

    def test_docstring_of_inherited_method(self):
        name = 'classmethodinA'
        f = new_function_in(name, taken_from_class='ClassA')
        assert f.docstring == 'class method docstring in Class A'

    def test_docstring_of_init(self):
        name = '__init__'
        f = new_function_in(name, 'ClassA', 'ClassA')
        assert f.docstring == ''

    def test_decorators(self):
        name = 'classmethodinA'
        f = new_function_in(name, taken_from_class='ClassA')
        assert f.decorators == ['@classmethod']

    @pytest.mark.parametrize("name, funcdef", [('get_attr6', 'def'), ('async_fun', 'async def')])
    def test_funcdef(self, name, funcdef):
        f = new_function_in(name)
        assert f.funcdef == funcdef

    def test_parameters(self):
        name = 'classmethod'
        obj = package_example.ClassB.__dict__[name]
        actual = list(inspect.signature(obj.__func__).parameters.values())[1:]
        f = new_function_in(name)
        assert f.parameters == actual

    def test_signature(self):
        name = 'classmethod'
        obj = package_example.ClassB.__dict__[name]
        expected = _PrettySignature.from_callable(obj.__func__)
        f = new_function_in(name)
        assert f.signature == expected

    def test_signature_object_init(self):
        f = Function('', '', object.__dict__['__init__'], ('', ''))
        assert f.signature == inspect.Signature()

    def test_signature_without_self(self):
        # like (a, b, c) -> bool
        name = 'classmethod'
        f = new_function_in(name)
        expected = f.signature.replace(parameters=list(f.signature.parameters.values())[1:])
        assert f.signature_without_self == expected

    # noinspection PyUnresolvedReferences
    @pytest.mark.parametrize("name, annotations, from_class", [('classmethod', __builtins__['bool'], 'ClassB'),
                                                               ('init_attr7', empty, 'ClassB'),
                                                               ('__init__', empty, 'ClassA')])
    def test_annotations(self, name, annotations, from_class):
        f = new_function_in(name, from_class, from_class)
        assert f.annotations == annotations

    def test_repr_classmethod(self):
        name = 'classmethod'
        f = new_function_in(name)
        assert repr(f) == '<@classmethod class def classmethod(\n    cls,\n    arg1: str,\n    arg2: int,\n    /,' \
                          '\n    arg3: int = 4,\n    *arg4,\n    arg5: int = 4,\n    arg6: float = 5\n) -> bool:' \
                          '  # class method docstri…>'

    def test_repr_staticmethod(self):
        name = 'staticmethod'
        f = new_function_in(name)
        assert repr(f) == '<@staticmethod static def staticmethod()>'

    def test_repr_method(self):
        name = 'get_attr6'
        modulename = 'package_example'
        qualname = f'ClassB.{name}'
        obj = getattr(package_example, 'ClassB').__dict__[name]
        f = Function(modulename, qualname, obj, (modulename, f'ClassA.{name}'))
        assert repr(f) == '<method def get_attr6(self, arg1, arg2, /):  ' \
                          '# inherited from package_example.ClassA.get_attr6, function docstring, …>'

    def test_repr_function(self):
        name = 'module_level_function'
        modulename = 'package_example'
        f = Function(modulename, name, package_example.__dict__['module_level_function'], (modulename, name))
        assert repr(f) == "<function def module_level_function(arg1, arg2='default', *, arg3, **kwargs) -> float:" \
                          "  # function docstring>"
