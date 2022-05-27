import pkgutil
import warnings
import traceback
from abc import abstractmethod
from types import ModuleType
from typing import Any, TypeVar, Callable
from importlib import import_module
from functools import cached_property
from inspect import getsource, getmodule, ismodule, isclass
from pdoc.doc_types import empty
from VPLCodeGenerator.inspect_util import is_package, safe_getattr
from .variable_parser import VariableParser


def obj_type(obj) -> str:
    """
    return `module` or 'class` and exception if not
    Parameters
    ----------
    obj: Any
        Python objects

    Returns
    -------
    type: str
          'module' or 'class'
    Raises
    -------
    Raises a Type error if the type of obj is neither `module` nor `class`.
    """
    if ismodule(obj):
        return 'module'
    elif isclass(obj):
        return 'class'
    else:
        t = type(obj)
        raise TypeError(f'This type ({t}) of object is not supported')


class SourceCodeParser:
    def __init__(self, obj: Any, encoding: str = 'utf-8') -> None:
        self.obj = obj
        self.type = obj_type(self.obj)
        self.code = getsource(self.obj)
        self.namespace = ''
        self._variable_parser = VariableParser(self.code, encoding)

    @cached_property
    @abstractmethod
    def var_docstring(self) -> dict[str, str]:
        """A mapping from member variable names to their docstrings."""

    @cached_property
    @abstractmethod
    def var_annotations(self) -> dict[str, str]:
        """A mapping from member variable names to their type annotations."""

    @cached_property
    def vars_sets(self) -> set[str]:
        return self.var_docstring.keys() | self.var_annotations.keys()

    @cached_property
    @abstractmethod
    def member_objects(self) -> dict[str, Any]:
        """A mapping from member names to their Python objects."""

    @cached_property
    def submodules(self):
        if not is_package(self.obj):
            return []


class SourceCodeModuleParser(SourceCodeParser):
    def __init__(self, obj: ModuleType, encoding: str = 'utf-8') -> None:
        super(SourceCodeModuleParser, self).__init__(obj, encoding)

    @cached_property
    def var_docstring(self) -> dict[str, str]:
        self._variable_parser.parse()
        return self._variable_parser.docstring_in_ns(self.namespace)

    @cached_property
    def var_annotations(self) -> dict[str, str]:
        """
        Or __annotations__ with Python 3.10
        References
        -------
        https://docs.python.org/3/howto/annotations.html#accessing-the-annotations-dict-of-an-object-in-python-3-10-and-newer
        """
        self._variable_parser.parse()
        return self._variable_parser.annotations_in_ns(self.namespace)

    @cached_property
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
                include_in = name in self.vars_sets or (
                        declared_in_this_module and not isinstance(obj, TypeVar)
                )
                if include_in:
                    members[name] = obj
            for name in self.var_docstring:
                members.setdefault(name, empty)
            # include submodules
            for module in self.submodules:
                members[module.__name__] = module
        return members

    @cached_property
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
