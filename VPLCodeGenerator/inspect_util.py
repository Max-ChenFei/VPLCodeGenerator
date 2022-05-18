from typing import Any
from types import ModuleType
import inspect
import warnings


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
        return inspect.getdoc(obj) or ''
    except Exception as e:
        warnings.warn(f"inspect.getdoc({obj!r}) raised an exception: {e!r}")
        return ""


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
