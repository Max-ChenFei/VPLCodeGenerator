"""
This module defines meta data analyser for Python objects.

There are four main types of meta data Analyser:

- `Module`
- `Class`
- `Function`
- `Variable`

All description types make heavy use of `@functools.cached_property` decorators.
This means they have a large set of attributes that are lazily computed on first access.
By convention, all attributes are read-only, although this is not enforced at runtime.

References
-------
This module is highly inspired by pdoc.doc.
.. https://github.com/mitmproxy/pdoc/blob/main/pdoc/doc.py
"""
from __future__ import annotations

import inspect
import re
import sys
import textwrap
import types
import warnings
from abc import ABCMeta, abstractmethod
from functools import wraps
from typing import Any, ClassVar, Generic, TypeVar, Union
from VPLCodeGenerator.inspect_util import safe_getattr, safe_getdoc, is_package
from pdoc import doc_ast, extract
from pdoc.doc_types import empty, safe_eval_type

from pdoc._compat import cache, cached_property, formatannotation, get_origin


def _include_fullname_in_traceback(f):
    """
    Doc.__repr__ should not raise, but it may raise if we screwed up.
    Debugging this is a bit tricky, because, well, we can't repr() in the traceback either then.
    This decorator adds location information to the traceback, which helps tracking down bugs.
    """

    @wraps(f)
    def wrapper(self):
        try:
            return f(self)
        except Exception as e:
            raise RuntimeError(f"Error in {self.fullname}'s repr!") from e

    return wrapper


T = TypeVar("T")


class Doc(Generic[T]):
    """
    A base class for all documentation objects.
    """

    modulename: str
    """
    The module that this object is in, for example `pdoc.doc`.
    """

    qualname: str
    """
    The qualified identifier name for this object. For example, if we have the following code:

    ```python
    class Foo:
        def bar(self):
            pass
    ```

    The qualname of `Foo`'s `bar` method is `Foo.bar`. The qualname of the `Foo` class is just `Foo`.

    See <https://www.python.org/dev/peps/pep-3155/> for details.
    """

    obj: T
    """
    The underlying Python object.
    """

    taken_from: tuple[str, str]
    """
    `(modulename, qualname)` of this doc object's original location.
    In the context of a module, this points to the location it was imported from,
    in the context of classes, this points to the class an attribute is inherited from.
    """

    def __init__(
            self, modulename: str, qualname: str, obj: T, taken_from: tuple[str, str]):
        """
        Initializes a documentation object, where
        `modulename` is the name this module is defined in,
        `qualname` contains a dotted path leading to the object from the module top-level, and
        `obj` is the object to document.
        """
        self.modulename = modulename
        self.qualname = qualname
        self.obj = obj
        self.taken_from = taken_from

    @cached_property
    def fullname(self) -> str:
        """The full qualified name of this doc object, for example `pdoc.doc.Doc`."""
        # qualname is empty for modules
        return f"{self.modulename}.{self.qualname}".rstrip(".").lstrip(".")

    @cached_property
    def name(self) -> str:
        """The name of this object. For top-level functions and classes, this is equal to the qualname attribute."""
        return self.fullname.split(".")[-1]

    @cached_property
    def docstring(self) -> str:
        """
        The docstring for this object. It has already been cleaned by `inspect.cleandoc`.

        If no docstring can be found, an empty string is returned.
        """
        return safe_getdoc(self.obj)

    @cached_property
    def is_inherited(self) -> bool:
        """
        If True, the doc object is inherited from another location.
        This most commonly refers to methods inherited by a subclass,
        but can also apply to variables that are assigned a class defined
        in a different module.
        """
        return (self.modulename, self.qualname) != self.taken_from

    @classmethod
    @property
    def type(cls) -> str:
        """
        The type of the doc object, either `"module"`, `"class"`, `"function"`, or `"variable"`.
        """
        return cls.__name__.lower()

    if sys.version_info < (3, 9):  # pragma: no cover
        # no @classmethod @property in 3.8
        @property
        def type(self) -> str:  # noqa
            return self.__class__.__name__.lower()


class Namespace(Doc[T], metaclass=ABCMeta):
    """
    A documentation object that can have children. In other words, either a module or a class.
    """

    def __init__(
            self, modulename: str, qualname: str, obj: T, taken_from: tuple[str, str], parser=None
    ):
        """
        Creates a documentation object given the actual
        Python module object.
        """
        super().__init__(modulename, qualname, obj, taken_from)
        self.parser = parser

    def __eq__(self, other):
        return type(self) == type(other) and self.modulename == other.modulename and self.qualname == other.qualname\
               and self.obj == other.obj and self.taken_from == other.taken_from and self.parser == other.parser

    def __hash__(self):
        return hash((self.modulename, self.qualname, self.obj, self.taken_from, self.parser))

    @cached_property
    def signature_without_self(self) -> inspect.Signature:
        """Like `signature`, but without the first argument.

        This is useful to display constructors.
        """
        return self.signature.replace(
            parameters=list(self.signature.parameters.values())[1:]
        )

    @cached_property
    def parameters(self) -> list[inspect.Parameter]:
        """ Parameters without the first parameter like `self`, `cls` and `/` as well as `*`"""
        return list(self.signature_without_self.parameters.values())

    @cached_property
    def members(self):
        return self.parser.members() if self.parser else []

    @cached_property
    @abstractmethod
    def own_members(self) -> list[Doc]:
        """A list of all own (i.e. non-inherited) members"""

    @cached_property
    def _members_by_origin(self) -> dict[tuple[str, str], list[Doc]]:
        """A mapping from (modulename, qualname) locations to the attributes taken from that path"""
        locations: dict[tuple[str, str], list[Doc]] = {}
        for member in self.members.values():
            mod, qualname = member.taken_from
            parent_qualname = ".".join(qualname.rsplit(".", maxsplit=1)[:-1])
            locations.setdefault((mod, parent_qualname), [])
            locations[(mod, parent_qualname)].append(member)
        return locations

    @cached_property
    def inherited_members(self) -> dict[tuple[str, str], list[Doc]]:
        """A mapping from (modulename, qualname) locations to the attributes inherited from that path"""
        return {
            k: v
            for k, v in self._members_by_origin.items()
            if k not in (self.taken_from, (self.modulename, self.qualname))
        }

    @cached_property
    def flattened_own_members(self) -> list[Doc]:
        """
        A list of all documented members and their child classes, recursively.
        """
        flattened = []
        for x in self.own_members:
            flattened.append(x)
            if isinstance(x, Class):
                flattened.extend(
                    [cls for cls in x.flattened_own_members if isinstance(cls, Class)]
                )
        return flattened

    @cache
    def get(self, identifier: str) -> Doc | None:
        """Returns the documentation object for a particular identifier, or `None` if the identifier cannot be found."""
        head, _, tail = identifier.partition(".")
        if tail:
            h = self.members.get(head, None)
            if isinstance(h, Class):
                return h.get(tail)
            return None
        else:
            return self.members.get(identifier, None)


class Module(Namespace[types.ModuleType]):
    """
    Representation of a module's documentation.
    """
    def __init__(
            self, modulename: str, qualname: str, obj: T, taken_from: tuple[str, str], parser=None
    ):
        """
        Creates a documentation object given the actual
        Python module object.
        """
        super().__init__(modulename, qualname, obj, taken_from, parser)

    @classmethod
    @cache
    def from_name(cls, name: str) -> Module:
        """Create a `Module` object by supplying the module's (full) name."""
        return cls(extract.load_module(name))

    @cache
    @_include_fullname_in_traceback
    def __repr__(self):
        return f"<module {self.fullname}{_docstr(self)}{_children(self)}>"

    @cached_property
    def is_package(self) -> bool:
        return is_package(self.obj)

    @cached_property
    def own_members(self) -> list[Doc]:
        return list(self.members.values())

    @cached_property
    def variables(self) -> list[Variable]:
        """
        A list of all documented module level variables.
        """
        return [x for x in self.members.values() if isinstance(x, Variable)]

    @cached_property
    def functions(self) -> list[Function]:
        """
        A list of all documented module level functions.
        """
        return [x for x in self.members.values() if isinstance(x, Function)]

    @cached_property
    def classes(self) -> list[Class]:
        """
        A list of all documented module level classes.
        """
        return [x for x in self.members.values() if isinstance(x, Class)]

    @cached_property
    def submodules(self) -> list[Module]:
        return self.parser.submodules()


class Class(Namespace[type]):
    """
    Representation of a class.
    """
    def __init__(self, modulename: str, qualname: str, obj: T, taken_from: tuple[str, str], parser=None):
        super(Class, self).__init__(modulename, qualname, obj, taken_from, parser)

    @cache
    @_include_fullname_in_traceback
    def __repr__(self):
        return f"<{_decorators(self)}class {self.modulename}.{self.qualname}{_docstr(self)}{_children(self)}>"

    @cached_property
    def signature(self) -> inspect.Signature:
        """
        The signature of __init__ in class. Example: (self, a, b, c) -> bool

        function.signature.parameters don't include `/` (for Positional_Only_Argumetns) and `*` (Keyword_Only_Arguments)
        str(function.signature) does include `/` and '*'

        This usually returns an instance of `_PrettySignature`, a subclass of `inspect.Signature`
        that contains pdoc-specific optimizations. For example, long argument lists are split over multiple lines
        in repr(). Additionally, all types are already resolved.

        If the signature cannot be determined, a placeholder Signature object is returned.
        """
        init_func = getattr(self.obj, '__init__')
        try:
            sig = _PrettySignature.from_callable(init_func)
        except Exception:
            return inspect.Signature(
                [inspect.Parameter("unknown", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
            )
        sig = sig.replace(return_annotation=empty)
        for p in sig.parameters.values():
            p._annotation = safe_eval_type(p.annotation, globalns, mod, self.fullname)  # type: ignore
        return sig

    @cached_property
    def bases(self) -> list[tuple[str, str, str]]:
        """
        A list of all base classes, i.e. all immediate parent classes.

        Each parent class is represented as a `(modulename, qualname, display_text)` tuple.
        """
        bases = []
        for x in safe_getattr(self.obj, "__orig_bases__", self.obj.__bases__):
            if x is object:
                continue
            o = get_origin(x)
            if o:
                bases.append((o.__module__, o.__qualname__, str(x)))
            elif x.__module__ == self.modulename:
                bases.append((x.__module__, x.__qualname__, x.__qualname__))
            else:
                bases.append(
                    (x.__module__, x.__qualname__, f"{x.__module__}.{x.__qualname__}")
                )
        return bases

    @cached_property
    def decorators(self) -> list[str]:
        """A list of all decorators the class is decorated with."""
        decorators = []
        for t in doc_ast.parse(self.obj).decorator_list:
            decorators.append(f"@{doc_ast.unparse(t)}")
        return decorators

    @cached_property
    def docstring(self) -> str:
        doc = Doc.docstring.__get__(self)  # type: ignore
        if doc == dict.__doc__:
            # Don't display default docstring for dict subclasses (primarily TypedDict).
            return ""
        else:
            return doc

    @cached_property
    def own_members(self) -> list[Doc]:
        members = self._members_by_origin.get((self.modulename, self.qualname), [])
        if self.taken_from != (self.modulename, self.qualname):
            # .taken_from may be != (self.modulename, self.qualname), for example when
            # a module re-exports a class from a private submodule.
            members += self._members_by_origin.get(self.taken_from, [])
        return members

    @cached_property
    def class_variables(self) -> list[Variable]:
        """
        A list of all documented class variables in the class.

        Class variables are variables that are explicitly annotated with `typing.ClassVar`.
        All other variables are treated as instance variables.
        """
        return [
            x
            for x in self.members.values()
            if isinstance(x, Variable) and x.is_classvar
        ]

    @cached_property
    def instance_variables(self) -> list[Variable]:
        """
        A list of all instance variables in the class.
        """
        return [
            x
            for x in self.members.values()
            if isinstance(x, Variable) and not x.is_classvar
        ]

    @cached_property
    def classmethods(self) -> list[Function]:
        """
        A list of all documented `@classmethod`s.
        """
        return [
            x
            for x in self.members.values()
            if isinstance(x, Function) and x.is_classmethod
        ]

    @cached_property
    def staticmethods(self) -> list[Function]:
        """
        A list of all documented `@staticmethod`s.
        """
        return [
            x
            for x in self.members.values()
            if isinstance(x, Function) and x.is_staticmethod
        ]

    @cached_property
    def methods(self) -> list[Function]:
        """
        A list of all documented methods in the class that are neither static- nor classmethods.
        """
        return [
            x
            for x in self.members.values()
            if isinstance(x, Function) and not x.is_staticmethod and not x.is_classmethod
        ]


if sys.version_info >= (3, 10):
    WrappedFunction = types.FunctionType | staticmethod | classmethod
else:  # pragma: no cover
    WrappedFunction = Union[types.FunctionType, staticmethod, classmethod]


class Function(Doc[types.FunctionType]):
    """
    Representation of a function's documentation.

    This class covers all "flavors" of functions, for example it also
    supports `@classmethod`s or `@staticmethod`s.
    """

    wrapped: WrappedFunction
    """The original wrapped function (e.g., `staticmethod(func)`)"""

    obj: types.FunctionType
    """The unwrapped "real" function."""

    def __init__(
            self,
            modulename: str,
            qualname: str,
            func: WrappedFunction,
            taken_from: tuple[str, str],
    ):
        """Initialize a function's documentation object."""
        unwrapped: types.FunctionType
        if isinstance(func, (classmethod, staticmethod)):
            unwrapped = func.__func__  # type: ignore
        else:
            unwrapped = func
        super().__init__(modulename, qualname, unwrapped, taken_from)
        self.wrapped = func

    def __eq__(self, other):
        return type(other) == Function and self.modulename == other.modulename \
               and self.qualname == other.qualname and self.wrapped == other.wrapped \
               and self.taken_from == other.taken_from

    def __hash__(self):
        return hash((self.modulename, self.qualname, self.wrapped, self.taken_from))

    @cache
    @_include_fullname_in_traceback
    def __repr__(self):
        if self.is_classmethod:
            t = "class"
        elif self.is_staticmethod:
            t = "static"
        elif self.qualname != safe_getattr(self.obj, "__name__", None):
            t = "method"
        else:
            t = "function"
        docstr = ''
        if _docstr(self) != '':
            docstr = f':{_docstr(self)}'
        return f"<{_decorators(self)}{t} {self.funcdef} {self.name}{self.signature}{docstr}>"

    @cached_property
    def docstring(self) -> str:
        doc = Doc.docstring.__get__(self)  # type: ignore
        if not doc:
            # inspect.getdoc fails for inherited @classmethods and unbound @property descriptors.
            # We now do an ugly dance to obtain the bound object instead,
            # that somewhat resembles what inspect._findclass is doing.
            cls = sys.modules.get(safe_getattr(self.obj, "__module__", None), None)
            for name in safe_getattr(self.obj, "__qualname__", "").split(".")[:-1]:
                cls = safe_getattr(cls, name, None)
            doc = safe_getdoc(safe_getattr(cls, self.name, None))

        if doc == object.__init__.__doc__:
            # inspect.getdoc(Foo.__init__) returns the docstring, for object.__init__ if left undefined...
            return ""
        else:
            return doc

    @cached_property
    def is_classmethod(self) -> bool:
        """
        `True` if this function is a `@classmethod`, `False` otherwise.
        """
        return isinstance(self.wrapped, classmethod)

    @cached_property
    def is_staticmethod(self) -> bool:
        """
        `True` if this function is a `@staticmethod`, `False` otherwise.
        """
        return isinstance(self.wrapped, staticmethod)

    @cached_property
    def decorators(self) -> list[str]:
        """A list of all decorators the function is decorated with."""
        decorators = []
        obj: types.FunctionType = self.obj  # type: ignore
        for t in doc_ast.parse(obj).decorator_list:
            decorators.append(f"@{doc_ast.unparse(t)}")
        return decorators

    @cached_property
    def funcdef(self) -> str:
        """
        The string of keywords used to define the function, i.e. `"def"` or `"async def"`.
        """
        if inspect.iscoroutinefunction(self.obj) or inspect.isasyncgenfunction(
                self.obj
        ):
            return "async def"
        else:
            return "def"

    @cached_property
    def signature(self) -> inspect.Signature:
        """
        The function's signature. Example: (self, a, b, c) -> bool

        function.signature.parameters don't include `/` (for Positional_Only_Argumetns) and `*` (Keyword_Only_Arguments)
        str(function.signature) does include `/` and '*'

        This usually returns an instance of `_PrettySignature`, a subclass of `inspect.Signature`
        that contains pdoc-specific optimizations. For example, long argument lists are split over multiple lines
        in repr(). Additionally, all types are already resolved.

        If the signature cannot be determined, a placeholder Signature object is returned.
        """
        if self.obj is object.__init__:
            # there is a weird edge case were inspect.signature returns a confusing (self, /, *args, **kwargs)
            # signature for the default __init__ method.
            return inspect.Signature()
        try:
            sig = _PrettySignature.from_callable(self.obj)
        except Exception:
            return inspect.Signature(
                [inspect.Parameter("unknown", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
            )
        mod = inspect.getmodule(self.obj)
        globalns = safe_getattr(mod, "__dict__", {})

        if self.name == "__init__":
            sig = sig.replace(return_annotation=empty)
        else:
            sig = sig.replace(
                return_annotation=safe_eval_type(
                    sig.return_annotation, globalns, mod, self.fullname
                )
            )
        for p in sig.parameters.values():
            p._annotation = safe_eval_type(p.annotation, globalns, mod, self.fullname)  # type: ignore
        return sig

    @cached_property
    def signature_without_self(self) -> inspect.Signature:
        """Like `signature`, but without the first argument.

        This is useful to display constructors.
        """
        return self.signature.replace(
            parameters=list(self.signature.parameters.values())[1:]
        )

    @cached_property
    def parameters(self) -> list[inspect.Parameter]:
        """ Parameters without the first parameter like `self`, `cls` and `/` as well as `*`"""
        return list(self.signature_without_self.parameters.values())

    @cached_property
    def annotations(self):
        return self.signature.return_annotation


class Variable(Doc[None]):
    """
    Representation of a variable's documentation. This includes module, class and instance variables.
    """

    default_value: Any | empty  # technically Any includes empty, but this conveys intent.
    """
    The variable's default value.

    In some cases, no default value is known. This may either be because a variable is only defined in the constructor,
    or it is only declared with a type annotation without assignment (`foo: int`).
    To distinguish this case from a default value of `None`, `pdoc.doc_types.empty` is used as a placeholder.
    """

    annotation: type | empty
    """
    The variable's type annotation.

    If there is no type annotation, `inspect_util.empty` is used as a placeholder.
    """

    def __init__(
            self,
            modulename: str,
            qualname: str,
            *,
            taken_from: tuple[str, str],
            docstring: str,
            annotation: type | empty = empty,
            default_value: Any | empty = empty,
            is_const: bool = True
    ):
        """
        Construct a variable doc object.

        While classes and functions can introspect themselves to see their docstring,
        variables can't do that as we don't have a "variable object" we could query.
        As such, docstring, declaration location, type annotation, and the default value
        must be passed manually in the constructor.
        """
        super().__init__(modulename, qualname, None, taken_from)
        # noinspection PyPropertyAccess
        self.docstring = inspect.cleandoc(docstring)
        self.annotation = annotation
        self.default_value = default_value
        self.is_const = is_const

    def __eq__(self, other):
        return type(other) == Variable and self.modulename == other.modulename \
               and self.qualname == other.qualname and self.taken_from == other.taken_from \
               and self.default_value == other.default_value

    def __hash__(self):
        return hash((self.modulename, self.qualname, self.default_value, self.taken_from))

    @cache
    @_include_fullname_in_traceback
    def __repr__(self):
        return f'<var {self.qualname.rsplit(".")[-1]}{self.annotation_str}{self.default_value_str}{_docstr(self)}>'

    @cached_property
    def is_classvar(self) -> bool:
        """`True` if the variable is a class variable, `False` otherwise."""
        if get_origin(self.annotation) is ClassVar:
            return True
        else:
            return False

    @cached_property
    def default_value_str(self) -> str:
        """The variable's default value as a pretty-printed str."""
        if self.default_value is empty:
            return ""
        else:
            try:
                return re.sub(
                    r" at 0x[0-9a-fA-F]+(?=>)",
                    "",
                    f" = {repr(self.default_value)}",
                )
            except Exception:
                return " = <unable to get value representation>"

    @cached_property
    def annotation_str(self) -> str:
        """The variable's type annotation as a pretty-printed str."""
        if self.annotation is not empty:
            return f": {formatannotation(self.annotation)}"
        else:
            return ""


class _PrettySignature(inspect.Signature):
    """
    A subclass of `inspect.Signature` that pads __str__ over several lines
    for complex signatures.
    """

    MULTILINE_CUTOFF = 70

    def _params(self) -> list[str]:
        """add forward slash and * in parameters list"""
        # redeclared here to keep code snipped below as-is.
        _POSITIONAL_ONLY = inspect.Parameter.POSITIONAL_ONLY
        _VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL
        _KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY

        # https://github.com/python/cpython/blob/799f8489d418b7f9207d333eac38214931bd7dcc/Lib/inspect.py#L3083-L3117
        # Change: added re.sub() to formatted = ....
        # ✂ start ✂
        result = []
        render_pos_only_separator = False
        render_kw_only_separator = True
        for param in self.parameters.values():
            formatted = re.sub(r" at 0x[0-9a-fA-F]+(?=>$)", "", str(param))

            kind = param.kind

            if kind == _POSITIONAL_ONLY:
                render_pos_only_separator = True
            elif render_pos_only_separator:
                # It's not a positional-only parameter, and the flag
                # is set to 'True' (there were pos-only params before.)
                result.append("/")
                render_pos_only_separator = False

            if kind == _VAR_POSITIONAL:
                # OK, we have an '*args'-like parameter, so we won't need
                # a '*' to separate keyword-only arguments
                render_kw_only_separator = False
            elif kind == _KEYWORD_ONLY and render_kw_only_separator:
                # We have a keyword-only parameter to render and we haven't
                # rendered an '*args'-like parameter before, so add a '*'
                # separator to the parameters list ("foo(arg1, *, arg2)" case)
                result.append("*")
                # This condition should be only triggered once, so
                # reset the flag
                render_kw_only_separator = False

            result.append(formatted)

        if render_pos_only_separator:
            # There were only positional-only parameters, hence the
            # flag was not reset to 'False'
            result.append("/")
        # ✂ end ✂

        return result

    def _return_annotation_str(self) -> str:
        if self.return_annotation is not empty:
            return formatannotation(self.return_annotation)
        else:
            return ""

    def __str__(self):
        result = self._params()
        return_annot = self._return_annotation_str()

        total_len = sum(len(x) + 2 for x in result) + len(return_annot)

        if total_len > self.MULTILINE_CUTOFF:
            rendered = "(\n    " + ",\n    ".join(result) + "\n)"
        else:
            rendered = "({})".format(", ".join(result))
        if return_annot:
            rendered += f" -> {return_annot}"

        return rendered


def _cut(x: str) -> str:
    """helper function for Doc.__repr__()"""
    if len(x) < 20:
        return x
    else:
        return x[:20] + "…"


def _docstr(doc: Doc) -> str:
    """helper function for Doc.__repr__()"""
    docstr = []
    if doc.is_inherited:
        if doc.taken_from:
            docstr.append(f"inherited from {'.'.join(doc.taken_from).rstrip('.')}")
    if doc.docstring:
        docstr.append(_cut(doc.docstring))
    if docstr:
        return f"  # {', '.join(docstr)}"
    else:
        return ""


def _decorators(doc: Class | Function) -> str:
    """helper function for Doc.__repr__()"""
    if doc.decorators:
        return " ".join(doc.decorators) + " "
    else:
        return ""


def _children(doc: Namespace) -> str:
    children = "\n".join(
        repr(x)
        for x in doc.members.values()
        if not x.name.startswith("_") or x.name == "__init__"
    )
    if children:
        children = f"\n{textwrap.indent(children, '    ')}"
    return children
