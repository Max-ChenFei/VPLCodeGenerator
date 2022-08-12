from abc import ABC, abstractmethod
from functools import cached_property


class Parser(ABC):

    @abstractmethod
    def var_docstring(self):
        NotImplementedError

    @abstractmethod
    def var_annotations(self):
        NotImplementedError

    @abstractmethod
    def member_objects(self):
        NotImplementedError

    def submodules(self):
        NotImplementedError

    @cached_property
    def vars_sets(self) -> set[str]:
        return self.var_docstring.keys() | self.var_annotations.keys()

    def definitions(self):
        """
            The mapping between object name to its modulename and qualname
        """
        NotImplementedError
