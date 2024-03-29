"""
    This parser extract definition of variable, functions, class and modueles from python objects.
"""
import enum
import pkgutil
import warnings
import traceback
import inspect
import types
from abc import abstractmethod
from types import ModuleType
from typing import Any, TypeVar, Callable
from importlib import import_module
from functools import cached_property
from inspect import getsource, getmodule, ismodule, isclass, isabstract, cleandoc
from VPLCodeGenerator.inspect_util import is_package, safe_getattr, empty, NonUserDefinedCallables
from VPLCodeGenerator.analyser import Doc, Module, Class, Function, Variable
from .variable_parser import VariableParser
from ..parser import Parser, ParserSuit
from pdoc.doc_types import resolve_annotations as pdoc_resolve_annotations, GenericAlias
from pdoc import doc_pyi


def resolve_annotations(obj: Any, annotations: dict[str, Any], fullname: str, ) -> dict[str, Any]:
    # try to resolve builtin types
    for k, v in annotations.items():
        try:
            annotations[k] = __builtins__[v]
        except:
            continue
    # some are in __annotations__
    for k, v in safe_getattr(obj, "__annotations__", {}).items():
        annotations[k] = v
    # other types
    return pdoc_resolve_annotations(annotations, obj, fullname)


class SourceCodeParserSuit(ParserSuit):
    def __init__(self):
        self.parser_types = {'default': SourceCodeModuleParser,
                             'module': SourceCodeModuleParser,
                             'class': SourceCodeClassParser}

    @staticmethod
    def name():
        return 'SourceCode'


class SourceCodeParser(Parser):
    def __init__(self, obj: Any, encoding: str = 'utf-8') -> None:
        self.obj = obj
        self.namespace = ''
        code = getsource(self.obj)
        self._variable_parser = VariableParser(code, encoding)
        if ismodule(obj):
            self.modulename = self.obj.__name__
            self.qualname = ''
        else:
            self.modulename = self.obj.__module__
            self.qualname = self.obj.__qualname__

    def __eq__(self, other):
        return type(self) == type(other) and self.obj == other.obj

    def __hash__(self):
        return hash(self.obj)

    @property
    def var_docstring(self) -> dict[str, str]:
        """A mapping from member variable names to their docstrings."""

    @property
    def var_annotations(self) -> dict[str, str]:
        """A mapping from member variable names to their type annotations."""

    def member_objects(self) -> dict[str, Any]:
        """A mapping from member names to their Python objects."""
        return {}

    def members(self) -> dict[str, Doc]:
        """A mapping from all members to their documentation objects.

        This mapping includes private members; they are only filtered out as part of the template logic.

        """
        members: dict[str, Doc] = {}
        for name, obj in self.member_objects().items():
            qualname = f"{self.qualname}.{name}".lstrip(".")
            taken_from = self._taken_from(name, obj)
            doc: Doc[Any]

            is_classmethod = isinstance(obj, classmethod)
            is_property = (
                    isinstance(obj, (property, cached_property))
                    or
                    # Python 3.9: @classmethod @property is now allowed.
                    is_classmethod
                    and isinstance(obj.__func__, (property, cached_property))
            )
            if is_property:
                func = obj
                if is_classmethod:
                    func = obj.__func__
                if isinstance(func, property):
                    func = func.fget
                else:
                    assert isinstance(func, cached_property)
                    func = func.func

                doc_f = Function(self.modulename, qualname, func, taken_from)
                doc = Variable(
                    self.modulename,
                    qualname,
                    docstring=doc_f.docstring,
                    annotation=doc_f.signature.return_annotation,
                    default_value=empty,
                    taken_from=taken_from,
                )
            elif inspect.isroutine(obj):
                doc = Function(self.modulename, qualname, obj, taken_from)  # type: ignore
            elif (
                    inspect.isclass(obj)
                    and obj is not empty
                    and not isinstance(obj, GenericAlias)
            ):
                # `dict[str,str]` is a GenericAlias instance. We want to render type aliases as variables though.
                doc = Class(self.modulename, qualname, obj, taken_from, SourceCodeClassParser(obj))
            elif inspect.ismodule(obj):
                doc = Module(obj)
            elif inspect.isdatadescriptor(obj):
                doc = Variable(
                    self.modulename,
                    qualname,
                    docstring=getattr(obj, "__doc__", None) or "",
                    annotation=self.var_annotations.get(name, empty),
                    default_value=empty,
                    taken_from=taken_from,
                )
            else:
                doc = Variable(
                    self.modulename,
                    qualname,
                    docstring="",
                    annotation=self.var_annotations.get(name, empty),
                    default_value=obj,
                    taken_from=taken_from,
                )
            if self.var_docstring.get(name):
                doc.docstring = self.var_docstring[name]
            members[doc.name] = doc

        if isinstance(self, Module):
            # quirk: doc_pyi expects .members to be set already
            self.members = members  # type: ignore
            doc_pyi.include_typeinfo_from_stub_files(self)

        return members

    def vars_sets(self) -> set[str]:
        return self.var_docstring.keys() | self.var_annotations.keys()


class SourceCodeModuleParser(SourceCodeParser):
    def __init__(self, obj: ModuleType, encoding: str = 'utf-8') -> None:
        super(SourceCodeModuleParser, self).__init__(obj, encoding)

    def _taken_from(self, member_name: str, obj: Any) -> tuple[str, str]:
        if obj is empty:
            return self.modulename, f"{self.qualname}.{member_name}".lstrip(".")
        if isinstance(obj, types.ModuleType):
            return obj.__name__, ""

        mod = safe_getattr(obj, "__module__", None)
        qual = safe_getattr(obj, "__qualname__", None)
        if mod and qual and "<locals>" not in qual:
            return mod, qual
        else:
            # This might be wrong, but it's the best guess we have.
            return (mod or self.modulename), f"{self.qualname}.{member_name}".lstrip(
                "."
            )

    @property
    def var_docstring(self) -> dict[str, str]:
        self._variable_parser.parse()
        return self._variable_parser.docstring_in_ns(self.namespace)

    @property
    def var_annotations(self) -> dict[str, str]:
        """
        Or __annotations__ with Python 3.10
        References
        -------
        https://docs.python.org/3/howto/annotations.html#accessing-the-annotations-dict-of-an-object-in-python-3-10-and-newer
        """
        self._variable_parser.parse()
        annotations = self._variable_parser.annotations_in_ns(self.namespace)
        return resolve_annotations(self.obj, annotations, self.obj.__name__)

    def member_objects(self) -> dict[str, Any]:
        """
        A mapping from member names to their Python objects.
        The member is either import object, class, function or attributes and submodule.
        References
        -------
        pdoc.doc https://github.com/mitmproxy/pdoc/blob/2fa71764eb175aa7b079db0c408e53f9c71fd7f3/pdoc/doc.py#L473-L519
        """
        members = {}

        all = safe_getattr(self.obj, "__all__", False)
        if all:
            for name in all:
                if name in self.obj.__dict__:
                    val = self.obj.__dict__[name]
                # __dict__ don't include the variable with only annotations. example: var: str
                elif name in self.var_annotations:
                    val = empty
                else:
                    # this may be an unimported submodule, try importing.
                    # (https://docs.python.org/3/tutorial/modules.html#importing-from-a-package)
                    try:
                        val = import_module(name)
                    except RuntimeError as e:
                        warnings.warn(
                            f"Found {name!r} in {self.obj.__name__}.__all__, but it does not resolve: {e}"
                        )
                        val = empty
                members[name] = val

        else:
            for name, obj in list(self.obj.__dict__.items()):
                # exclude imported objects, only a TypeVar,
                obj_module = getmodule(obj)
                declared_in_this_module = self.obj.__name__ == safe_getattr(
                    obj_module, "__name__", None
                )
                # exclude variable without annotation or docstring
                # exclude TypeVar
                # If one needs to pickup one of these things, __all__ is the correct way.
                include_in = name in self.vars_sets() or (
                        declared_in_this_module and not isinstance(obj, TypeVar)
                )
                if include_in:
                    members[name] = obj
            for name in self.var_docstring:
                members.setdefault(name, empty)
        return members

    def submodules(self) -> list[ModuleType]:
        """
        A list of all (direct) subdir.
        References
        -------
        pdoc.doc https://github.com/mitmproxy/pdoc/blob/2fa71764eb175aa7b079db0c408e53f9c71fd7f3/pdoc/doc.py#L431-L466
        """
        if not is_package(self.obj):
            return []
        include: Callable[[str], bool]
        mod_all = safe_getattr(self.obj, "__all__", False)
        if mod_all is not False:
            mod_all_pos = {name: i for i, name in enumerate(mod_all)}
            include = mod_all_pos.__contains__
        else:

            def include(name: str) -> bool:
                # optimization: we don't even try to load modules starting with an underscore as they would not be
                # visible by default. The downside of this is that someone who overrides `is_public` will miss those
                # entries, the upsides are 1) better performance and 2) less warnings because of import failures
                # (think of OS-specific modules, e.g. _linux.py failing to import on Windows).
                return not name.startswith("_")

        submodules = []
        for mod in pkgutil.iter_modules(self.obj.__path__, f"{self.obj.__name__}."):
            _, _, mod_name = mod.name.rpartition(".")
            if not include(mod_name):
                continue
            try:
                module = import_module(mod.name)
            except RuntimeError:
                warnings.warn(f"Couldn't import {mod.name}:\n{traceback.format_exc()}")
                continue
            submodules.append(module)
        return submodules


class SourceCodeClassParser(SourceCodeParser):
    def __init__(self, obj: Any, encoding: str = 'utf-8') -> None:
        super(SourceCodeClassParser, self).__init__(obj, encoding)
        self.namespace = self.obj.__name__
        self._var_annotations: dict[str, str] = {}
        self._var_docstring: dict[str, str] = {}
        self._definitions: dict[str, tuple[str, str]] = {}
        self._var_docstring_annotations_in_inheritance_chain()

    def _var_docstring_annotations_in_inheritance_chain(self):
        """
        Get docstring and annotations of all variables including inherited ones.
        The variables inherited from base class and declared in __init__ can not be accessed via `class.__dict__`, so
        we parse the source code again.
        """
        # variable in current object
        self._variable_parser.parse()
        self._var_docstring = self._variable_parser.docstring_in_ns(self.namespace)
        self._var_annotations = self._variable_parser.annotations_in_ns(self.namespace)
        for name in self._var_docstring.keys() | self._var_annotations.keys():
            self._definitions.setdefault(name, (self.obj.__module__, f"{self.obj.__qualname__}.{name}"))
        # variable inherited from base class
        for cls in self.obj.__mro__[1:]:  # remove the current class
            if cls == object:
                continue
            p = SourceCodeClassParser(cls)
            for name, docstr in p.var_docstring.items():
                self._var_docstring.setdefault(name, docstr)
            for name, annot in p._var_annotations.items():
                self._var_annotations.setdefault(name, annot)
            for name in p.var_docstring.keys() | p._var_annotations.keys():
                self._definitions.setdefault(name, (cls.__module__, f"{cls.__qualname__}.{name}"))

    @property
    def definitions(self):
        self.member_objects()
        return self._definitions

    @property
    def var_docstring(self) -> dict[str, str]:
        """A mapping from member variable names to their docstrings including inherited variables."""
        return self._var_docstring

    @property
    def var_annotations(self) -> dict[str, str]:
        """A mapping from member variable names to their type annotations including inherited variables.
         `__annotations__` from Python 3.10 does not inlcude inherited variables and ones in the `__init__`"""
        annotations = self._var_annotations
        return resolve_annotations(self.obj, annotations, self.obj.__qualname__)

    def member_objects(self) -> dict[str, Any]:
        """
        A mapping from member names to their Python objects.
        The member name is either function, attributes (declared outside the __init__)
        References
        -------
        https://github.com/mitmproxy/pdoc/blob/2fa71764eb175aa7b079db0c408e53f9c71fd7f3/pdoc/doc.py#L636-L687
        """
        members: dict[str, Any] = {}
        for cls in self.obj.__mro__:
            if cls == object:
                continue
            for name, obj in cls.__dict__.items():
                members.setdefault(name, obj)
                self._definitions[name] = (cls.__module__, f"{cls.__qualname__}.{name}")
        # use value from the current class not its base class
        for attr in ['__init__', '__doc__', '__annotations__', '__dict__', '__module__']:
            members[attr] = getattr(self.obj, attr)
            self._definitions[attr] = (self.obj.__module__, f"{self.obj.__qualname__}.{attr}")
        if '__doc__' in members.keys() and members['__doc__'] is not None:
            members['__doc__'] = cleandoc(members['__doc__'])

        # include variables declared in __init__ and only with annotations without assigment (not in __dict__)
        for name in self.vars_sets():
            try:
                v = self.obj[name]
            except:
                v = empty
            members.setdefault(name, v)

        init_has_no_doc = members.get("__init__", object.__init__).__doc__ in (
            None,
            object.__init__.__doc__,
        )
        if init_has_no_doc:
            if isabstract(self.obj):
                # Special case: We don't want to show constructors for abstract base classes unless
                # they have a custom docstring.
                del members["__init__"]
            elif issubclass(self.obj, enum.Enum):
                # Special case: Do not show a constructor for enums. They are typically not constructed by users.
                # The alternative would be showing __new__, as __call__ is too verbose.
                del members["__init__"]
            elif issubclass(self.obj, dict):
                # Special case: Do not show a constructor for dict subclasses.
                del members["__init__"]
            else:
                # Check if there's a helpful Metaclass.__call__ or Class.__new__. This dance is very similar to
                # https://github.com/python/cpython/blob/9feae41c4f04ca27fd2c865807a5caeb50bf4fc4/Lib/inspect.py#L2359-L2376
                call = safe_getattr(type(self.obj), "__call__", None)
                custom_call_with_custom_docstring = (
                        call is not None
                        and not isinstance(call, NonUserDefinedCallables)
                        and call.__doc__ not in (None, object.__call__.__doc__)
                )
                if custom_call_with_custom_docstring:
                    members["__init__"] = call
                else:
                    # Does our class define a custom __new__ method?
                    new = safe_getattr(self.obj, "__new__", None)
                    custom_new_with_custom_docstring = (
                            new is not None
                            and not isinstance(new, NonUserDefinedCallables)
                            and new.__doc__ not in (None, object.__new__.__doc__)
                    )
                    if custom_new_with_custom_docstring:
                        members["__init__"] = new

        return members

    def _taken_from(self, member_name: str, obj: Any) -> tuple[str, str]:
        try:
            return self.definitions[member_name]
        except KeyError:  # pragma: no cover
            # TypedDict botches __mro__ and may need special casing here.
            warnings.warn(
                f"Cannot determine where {self.fullname}.{member_name} is taken from, assuming current file."
            )
            return self.modulename, f"{self.qualname}.{member_name}"
