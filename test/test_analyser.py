import inspect
import pytest
from typing import ClassVar
from test_data import package_example
# noinspection PyProtectedMember
from VPLCodeGenerator.analyser import Variable, Function, Class, equal, _docstr, _cut, _PrettySignature
from VPLCodeGenerator.inspect_util import empty
from VPLCodeGenerator.parser import SourceCodeClassParser


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


builtins_types = {'float': __builtins__['float'],
                  'bool': __builtins__['bool'],
                  'str': __builtins__['str']}


class TestClass:
    classA = package_example.ClassA
    classB = package_example.ClassB
    submoduleC = package_example.SubmoduleC
    submoduleB = package_example.submodule_b.SubmoduleB
    parsers = {'class': SourceCodeClassParser}

    @pytest.mark.parametrize("obj, modulename, base", [(classA, '', []),
                                                       (classB, classB.__module__,
                                                        [(classA.__module__, 'ClassA', 'ClassA')]),
                                                       (submoduleC, submoduleC.__module__,
                                                        [(submoduleB.__module__, 'SubmoduleB',
                                                          f"{submoduleB.__module__}.SubmoduleB")])])
    def test_base(self, obj, modulename, base):
        parsers = {'class': SourceCodeClassParser}
        c = Class(modulename, '', obj, ('', ''), parsers)
        assert c.bases == base

    def setup_method(self):
        modulename = package_example.ClassB.__module__
        self.c = Class(modulename, 'ClassB', self.classB, (modulename, 'ClassB'), self.parsers)

    def test_base_object(self):
        modulename = package_example.__name__
        qualname = package_example.ClassB.__qualname__
        obj = package_example.ClassB
        c = Class(modulename, qualname, obj, (modulename, qualname), self.parsers)
        assert c.bases == [(modulename, package_example.ClassA.__name__, package_example.ClassA.__name__)]

    def test_decorators(self):
        assert self.c.decorators == ['@final']

    def test_docstring(self):
        assert self.c.docstring == inspect.getdoc(package_example.ClassB)

    def test_docstring_dict(self):
        class DictSubclass(dict):
            pass

        c = Class('', '', DictSubclass(), ('', ''), None)
        assert c.docstring == ''

    def test_taken_from(self):
        assert self.c._taken_from('test', None) == ('test_data.package_example', 'ClassB.test')

    @pytest.fixture
    def expected_members(self):
        return {'attr0': Variable('test_data.package_example', 'ClassB.attr0',
                                  taken_from=('test_data.package_example', 'ClassA.attr0'), docstring='',
                                  annotation=builtins_types['str']),
                'attr1': Variable('test_data.package_example', 'ClassB.attr1',
                                  taken_from=('test_data.package_example', 'ClassA.attr1'),
                                  docstring='doc comment after assignment',
                                  default_value='attr1_v'),
                'attr2': Variable('test_data.package_example', 'ClassB.attr2',
                                  taken_from=('test_data.package_example', 'ClassA.attr2'),
                                  docstring='doc comment before assignment'),
                'attr3': Variable('test_data.package_example', 'ClassB.attr3',
                                  taken_from=('test_data.package_example', 'ClassA.attr3'),
                                  annotation=builtins_types['float'],
                                  docstring='attribute docstring'),
                'attr4': Variable('test_data.package_example', 'ClassB.attr4',
                                  taken_from=('test_data.package_example', 'ClassA.attr4'),
                                  docstring='attribute multiple\n line docstring',
                                  annotation=builtins_types['str']),
                'attr5': Variable('test_data.package_example', 'ClassB.attr5',
                                  taken_from=('test_data.package_example', 'ClassA.attr5'),
                                  docstring='the string followed by a attribute',
                                  annotation=builtins_types['str']),
                'attr8': Variable('test_data.package_example', 'ClassB.attr8',
                                  taken_from=('test_data.package_example', 'ClassB.attr8'),
                                  docstring='This is class attr',
                                  annotation=ClassVar[str],
                                  default_value='class attr 8'),
                'update_attr3': Function('test_data.package_example', 'ClassB.update_attr3',
                                         package_example.ClassB.update_attr3,
                                         ('test_data.package_example', 'ClassA.update_attr3')),
                'classmethodinA': Function('test_data.package_example', 'ClassB.classmethodinA',
                                           package_example.ClassA.__dict__['classmethodinA'],
                                           ('test_data.package_example', 'ClassA.classmethodinA')),
                'ClassC': Class('test_data.package_example', 'ClassB.ClassC', package_example.ClassB.ClassC,
                                ('test_data.package_example', 'ClassA.ClassC'), self.parsers),
                'staticmethod': Function('test_data.package_example', 'ClassB.staticmethod',
                                         package_example.ClassB.__dict__['staticmethod'],
                                         ('test_data.package_example', 'ClassB.staticmethod')),
                'classmethod': Function('test_data.package_example', 'ClassB.classmethod',
                                        package_example.ClassB.__dict__['classmethod'],
                                        ('test_data.package_example', 'ClassB.classmethod')),
                'init_attr7': Function('test_data.package_example', 'ClassB.init_attr7',
                                       package_example.ClassB.init_attr7,
                                       ('test_data.package_example', 'ClassB.init_attr7')),
                'get_attr6': Function('test_data.package_example', 'ClassB.get_attr6',
                                      package_example.ClassB.get_attr6,
                                      ('test_data.package_example', 'ClassA.get_attr6')),
                'async_fun': Function('test_data.package_example', 'ClassB.async_fun',
                                      package_example.ClassB.async_fun,
                                      ('test_data.package_example', 'ClassB.async_fun')),
                '__weakref__': Variable('test_data.package_example', 'ClassB.__weakref__',
                                        taken_from=('test_data.package_example', 'ClassA.__weakref__'),
                                        docstring='list of weak references to the object (if defined)'),
                '__init__': Function('test_data.package_example', 'ClassB.__init__',
                                     package_example.ClassB.__init__,
                                     ('test_data.package_example', 'ClassB.__init__')),
                '__module__': Variable('test_data.package_example', 'ClassB.__module__',
                                       taken_from=('test_data.package_example', 'ClassB.__module__'),
                                       docstring='',
                                       default_value='test_data.package_example'),
                '__annotations__': Variable('test_data.package_example', 'ClassB.__annotations__',
                                            taken_from=('test_data.package_example', 'ClassB.__annotations__'),
                                            docstring='',
                                            default_value=package_example.ClassB.__annotations__),
                '__doc__': Variable('test_data.package_example', 'ClassB.__doc__',
                                    taken_from=('test_data.package_example', 'ClassB.__doc__'),
                                    docstring='',
                                    default_value='This is the B class docstring.\nIt is derived from A.'),
                '__dict__': Variable('test_data.package_example', 'ClassB.__dict__',
                                     taken_from=('test_data.package_example', 'ClassB.__dict__'),
                                     docstring='',
                                     default_value=package_example.ClassB.__dict__)}

    @pytest.fixture
    def own_members(self):
        return {'attr8': Variable('test_data.package_example', 'ClassB.attr8',
                                  taken_from=('test_data.package_example', 'ClassB.attr8'),
                                  docstring='This is class attr',
                                  annotation=ClassVar[str],
                                  default_value='class attr 8'),
                'staticmethod': Function('test_data.package_example', 'ClassB.staticmethod',
                                         package_example.ClassB.__dict__['staticmethod'],
                                         ('test_data.package_example', 'ClassB.staticmethod')),
                'classmethod': Function('test_data.package_example', 'ClassB.classmethod',
                                        package_example.ClassB.__dict__['classmethod'],
                                        ('test_data.package_example', 'ClassB.classmethod')),
                'init_attr7': Function('test_data.package_example', 'ClassB.init_attr7',
                                       package_example.ClassB.init_attr7,
                                       ('test_data.package_example', 'ClassB.init_attr7')),
                'async_fun': Function('test_data.package_example', 'ClassB.async_fun',
                                      package_example.ClassB.async_fun,
                                      ('test_data.package_example', 'ClassB.async_fun')),
                '__init__': Function('test_data.package_example', 'ClassB.__init__',
                                     package_example.ClassB.__init__,
                                     ('test_data.package_example', 'ClassB.__init__')),
                '__module__': Variable('test_data.package_example', 'ClassB.__module__',
                                       taken_from=('test_data.package_example', 'ClassB.__module__'),
                                       docstring='',
                                       default_value='test_data.package_example'),
                '__annotations__': Variable('test_data.package_example', 'ClassB.__annotations__',
                                            taken_from=('test_data.package_example', 'ClassB.__annotations__'),
                                            docstring='',
                                            default_value=package_example.ClassB.__annotations__),
                '__doc__': Variable('test_data.package_example', 'ClassB.__doc__',
                                    taken_from=('test_data.package_example', 'ClassB.__doc__'),
                                    docstring='',
                                    default_value='This is the B class docstring.\nIt is derived from A.'),
                '__dict__': Variable('test_data.package_example', 'ClassB.__dict__',
                                     taken_from=('test_data.package_example', 'ClassB.__dict__'),
                                     docstring='',
                                     default_value=package_example.ClassB.__dict__)}

    @pytest.fixture
    def inherited_members(self):
        return {'attr0': Variable('test_data.package_example', 'ClassB.attr0',
                                  taken_from=('test_data.package_example', 'ClassA.attr0'), docstring='',
                                  annotation=builtins_types['str']),
                'attr1': Variable('test_data.package_example', 'ClassB.attr1',
                                  taken_from=('test_data.package_example', 'ClassA.attr1'),
                                  docstring='doc comment after assignment',
                                  default_value='attr1_v'),
                'attr2': Variable('test_data.package_example', 'ClassB.attr2',
                                  taken_from=('test_data.package_example', 'ClassA.attr2'),
                                  docstring='doc comment before assignment'),
                'attr3': Variable('test_data.package_example', 'ClassB.attr3',
                                  taken_from=('test_data.package_example', 'ClassA.attr3'),
                                  annotation=builtins_types['float'],
                                  docstring='attribute docstring'),
                'attr4': Variable('test_data.package_example', 'ClassB.attr4',
                                  taken_from=('test_data.package_example', 'ClassA.attr4'),
                                  docstring='attribute multiple\n line docstring',
                                  annotation=builtins_types['str']),
                'attr5': Variable('test_data.package_example', 'ClassB.attr5',
                                  taken_from=('test_data.package_example', 'ClassA.attr5'),
                                  docstring='the string followed by a attribute',
                                  annotation=builtins_types['str']),
                'update_attr3': Function('test_data.package_example', 'ClassB.update_attr3',
                                         package_example.ClassB.update_attr3,
                                         ('test_data.package_example', 'ClassA.update_attr3')),
                'classmethodinA': Function('test_data.package_example', 'ClassB.classmethodinA',
                                           package_example.ClassA.__dict__['classmethodinA'],
                                           ('test_data.package_example', 'ClassA.classmethodinA')),
                'ClassC': Class('test_data.package_example', 'ClassB.ClassC', package_example.ClassB.ClassC,
                                ('test_data.package_example', 'ClassA.ClassC'), self.parsers),

                'get_attr6': Function('test_data.package_example', 'ClassB.get_attr6',
                                      package_example.ClassB.get_attr6,
                                      ('test_data.package_example', 'ClassA.get_attr6')),
                '__weakref__': Variable('test_data.package_example', 'ClassB.__weakref__',
                                        taken_from=('test_data.package_example', 'ClassA.__weakref__'),
                                        docstring='list of weak references to the object (if defined)'),
                }

    def test_members(self, expected_members):
        actual = self.c.members
        expected = expected_members
        for k in actual.keys():
            assert equal(actual[k], expected[k])

    def test_own_members(self, own_members):
        actual = self.c.own_members
        expected = own_members
        for m in actual:
            assert equal(m, expected[m.name])

    def test_inherited_members(self, inherited_members):
        actual = self.c.inherited_members
        for m in actual[('test_data.package_example', 'ClassA')]:
            assert equal(m, inherited_members[m.name])

    def test_class_variables(self):
        actual = self.c.class_variables
        expected = Variable('test_data.package_example', 'ClassB.attr8',
                            taken_from=('test_data.package_example', 'ClassB.attr8'),
                            docstring='This is class attr',
                            annotation=ClassVar[str],
                            default_value='class attr 8')
        assert equal(actual[0], expected)

    def test_instance_variables(self, expected_members):
        actual = self.c.instance_variables
        variables = {}
        for m in expected_members.values():
            if isinstance(m, Variable) and not m.is_classvar:
                variables[m.name] = m
        assert len(actual) == len(variables)
        for v in actual:
            assert equal(v, variables[v.name])

    def test_methods(self, expected_members):
        actual = self.c.methods
        expectd = {
            x.name: x
            for x in expected_members.values()
            if isinstance(x, Function) and not x.is_staticmethod and not x.is_classmethod
        }
        assert len(actual) == len(expectd)
        for f in actual:
            assert equal(f, expectd[f.name])

    def test_classmethods(self, expected_members):
        actual = self.c.classmethods
        expectd = {
            x.name: x
            for x in expected_members.values()
            if isinstance(x, Function) and x.is_classmethod
        }
        assert len(actual) == len(expectd)
        for f in actual:
            assert equal(f, expectd[f.name])

    def test_staticmethods(self, expected_members):
        actual = self.c.staticmethods
        expectd = {
            x.name: x
            for x in expected_members.values()
            if isinstance(x, Function) and x.is_staticmethod
        }
        assert len(actual) == len(expectd)
        for f in actual:
            assert equal(f, expectd[f.name])
