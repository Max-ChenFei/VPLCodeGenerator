from typing import Any
from types import ModuleType
import inspect
import warnings

empty = inspect.Signature.empty  # type: ignore

# adapted from
# pdoc.types.py
# https://github.com/python/cpython/blob/9feae41c4f04ca27fd2c865807a5caeb50bf4fc4/Lib/inspect.py#L1740-L1747
# ✂ start ✂
BuiltinFunctionType = type(len)
_WrapperDescriptor = type(type.__call__)
_MethodWrapper = type(all.__call__)  # type: ignore
_ClassMethodWrapper = type(int.__dict__["from_bytes"])

NonUserDefinedCallables = (
    _WrapperDescriptor,
    _MethodWrapper,
    _ClassMethodWrapper,
    BuiltinFunctionType,
)
# ✂ end ✂


def safe_getattr(obj: Any, attr_name: str, default=None) -> Any:
    """
    Get a named attribute from an object without any exception.
    default argument is returned when the attribute doesn't exist.
    Parameters
    ----------
    obj : Any
          The python object
    attr_name : str
          The name of attribute
    default : Any or None
          The default value when the attribute doesn't exist.
    Returns
    -------
    out: Any
        the attribute of an object if it is exist, or the default argument if it is not existed.
    References
    -------
    .. https://github.com/mitmproxy/pdoc/blob/main/pdoc/doc.py#L1129-L1137
    """
    try:
        return getattr(obj, attr_name, default)
    except Exception as e:
        warnings.warn(f"getattr({obj!r}, {attr_name!r}, {default!r}) raised an exception: {e!r}")
        return default


def safe_getdoc(obj: Any) -> str:
    """
    get docstring of python object without any exception.
    default empty string is returned when the docstring doesn't exist.
    Parameters
    ----------
    obj : Any
          The python object
    Returns
    -------
    out: Str
         the docstring of an object if it is exist, or the empty string if it is not existed.
    References
    -------
    .. https://github.com/mitmproxy/pdoc/blob/main/pdoc/doc.py#L1140-L1148
    """
    try:
        doc = inspect.getdoc(obj) or ''
    except Exception as e:
        warnings.warn(f"inspect.getdoc({obj!r}) raised an exception: {e!r}")
        return ""
    else:
        return doc.strip()


def get_allattr(obj: ModuleType) -> Any:
    """
    Get __all__ attribute of the module.
    Parameters
    ----------
    obj : ModuleType
          The python module
    Returns
    -------
    out: Any
         The __all__ attribute of the module, or None if given obj does not have __all__.
    Raises
    ------
    ValueError
         if given obj have invalid __all__.
    References
    -------
    .. https://github.com/sphinx-doc/sphinx/blob/5.x/sphinx/util/inspect.py#L73-L86
    """
    __all__ = safe_getattr(obj, '__all__', None)
    if __all__ is None:
        return None
    else:
        if isinstance(__all__, (list, tuple)) and all(isinstance(e, str) for e in __all__):
            return __all__
        else:
            raise ValueError(__all__)


def is_package(obj: Any) -> bool:
    """
          `True` if the module is a package, `False` otherwise.

          Packages are a special kind of module that may have subdir.
          Typically, this means that this file is in a directory named like the
          module with the name `__init__.py`.
          """
    return safe_getattr(obj, "__path__", None) is not None


def dedent(source: str) -> str:
    """
    Dedent the head of a function or class definition so that it can be parsed by `ast.parse`.
    This is an alternative to `textwrap.dedent`, which does not dedent if there are docstrings
    without indentation. For example, this is valid Python code but would not be dedented with `textwrap.dedent`:

    class Foo:
        def bar(self):
           '''
    this is a docstring
           '''
    """
    if not source or source[0] not in (" ", "\t"):
        return source
    source = source.lstrip()
    # we may have decorators before our function definition, in which case we need to dedent a few more lines.
    # the following heuristic should be good enough to detect if we have reached the definition.
    # it's easy to produce examples where this fails, but this probably is not a problem in practice.
    if not any(source.startswith(x) for x in ["async ", "def ", "class "]):
        first_line, rest = source.split("\n", 1)
        return first_line + "\n" + dedent(rest)
    else:
        return source