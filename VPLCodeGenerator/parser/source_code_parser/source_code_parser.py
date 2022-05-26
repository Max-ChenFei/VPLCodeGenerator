from abc import abstractmethod
from typing import Any
from functools import cached_property
from inspect import getsource, ismodule, isclass
from VPLCodeGenerator.inspect_util import is_package
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
    def _vars_sets(self) -> set[str]:
        return self.var_docstring.keys() | self.var_annotations.keys()

    @cached_property
    @abstractmethod
    def member_objects(self) -> dict[str, Any]:
        """A mapping from member names to their Python objects."""

    def submodules(self):
        if not is_package(self.obj):
            return []
