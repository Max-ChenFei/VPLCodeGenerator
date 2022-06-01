import os
from typing import ClassVar
from .subdir import submodule_a
from . import submodule_b, subpackage
from .subpackage import *  # import SubmoduleC

# `numpy` represents the module that not imported
__all__ = ['submodule_a', 'submodule_b', 'ClassA', 'SubmoduleC',
            'numpy', 'module_level_function', 'var1', 'var2', 'instance_of_a']

name = 'This is a package'


def module_level_function(arg1, arg2='default', *args, **kwargs) -> float:
    """function docstring"""
    v = arg1 * 2
    return v


class ClassA(object):
    """A class docstring"""
    attr0: str  # only type annotations
    attr1 = 'attr1_v'  #: doc comment after assignment

    def __init__(self, attr):
        #: doc comment before assignment
        self.attr2 = attr
        self.attr3: float = 3
        """attribute docstring"""
        self.attr4: str = 'attr4_v'
        """
            attribute multiple
            line docstring
        """
        self.attr5: str = 'attr5_v'
        "the string followed by a attribute"

    def update_attr3(self, new):
        # type: (float) -> float
        self.attr3 = new
        return self.attr3

    def get_attr6(self):
        self.attr6 = None
        return self.attr6

    class ClassC:
        attr1: None = None  #: nested class attributes comment


#: doc comment before assignment first line
#: doc comment before assignment second line
instance_of_a: ClassA = ClassA('sample_instance')

var1: float = 3.1415925  #: doc comment after assignment
var2: str  # this is a comment. This will only be accessed via var_annotations, not via __dict__ and var_docstring
var3: int = 3
"""variable docstring"""
var4: list = ['a', 'b', 'c']
"""
    variable multiple
    line docstring
"""
var5 = {'k': 'v'}
"the string followed by a attribute"

from typing import final


@final
class ClassB(ClassA):
    """This is the B class docstring.
       It is derived from A.
    """
    attr8: ClassVar[str] = 'class attr 8'  #: This is class attr

    @staticmethod
    def staticmethod():
        return True

    @classmethod
    def classmethod(cls) -> bool:
        """
        class method docstring
        """
        return True

    def init_attr7(self):
        self.attr7: float = 5  #: attr7 not in __init__ function

    def get_attr6(self):
        """function docstring, Overrides version from class A"""
        return self.attr6


instance_of_b = ClassB('sample_instance')  # comment, not doc comment

module_level_function(2)
