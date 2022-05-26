from typing import Dict, Tuple
from functools import cache
from sphinx.pycode.parser import Parser


class VariableParser:
    """The parser picks up variable docstring(comment) and annotations in current module or class,
    not including the inherited variables. The `inspect.get_annotations` is not used because the variables
    in `__init__`` can not be collected.
    """

    def __init__(self, code: str, encoding: str = 'utf-8') -> None:
        self.code = code
        self.encoding = encoding
        self.annotations: Dict[Tuple[str, str], str] = {}
        """
           The mapping between a variable name and its annotations.
           The key is a Tuple[namespace, variable name]. the top level namespace is ''.
           The value is the annotation.
        """
        self.docstring: Dict[Tuple[str, str], str] = {}
        """
           The mapping between the variable and its docstring (comment).
           The key is a Tuple[variable's parent qualname, variable name].
           The value is the docstring (comment).
        """
        self._parsed = False

    def parse(self) -> None:
        """parer the source code and store the variable docstring(comments),
           annotations in class attributes
        """
        if self._parsed:
            return
        self._parsed = True
        p = Parser(self.code, self.encoding)
        p.parse_comments()
        self.annotations = p.annotations
        self.docstring = dict(p.comments)

    def _value_in_ns(self, d: Dict[Tuple[str, str], str], ns: str):
        out: Dict[str, str] = {}
        for (namespace, name), value in d.items():
            if namespace == ns:
                out[name] = value
        return out

    @cache
    def annotations_in_ns(self, ns: str = '') -> Dict[str, str]:
        """
        Return the variable names and their annotations in the namespace
        Parameters
        ----------
        ns: str
            The current namespace that be queried.

        Returns
        -------
        out: Dict[str, str]
             The mapping between a variable name and its annotations in the namespace.
        """
        self.parse()
        return self._value_in_ns(self.annotations, ns)

    @cache
    def docstring_in_ns(self, ns: str = '') -> Dict[str, str]:
        """
        Return the variable names and their docstring in the namespace
        Parameters
        ----------
        ns: str
            The current namespace that be queried.

        Returns
        -------
        out: Dict[str, str]
             The mapping between a variable name and its docstring in the namespace.
        """
        self.parse()
        return self._value_in_ns(self.docstring, ns)
