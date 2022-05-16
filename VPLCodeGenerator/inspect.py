from typing import Any
import warnings


def safe_getattr(obj: Any, attr_name: str, default=None) -> Any:
    """
    get attribute of obj without any exception
    """
    try:
        return getattr(obj, attr_name, default)
    except Exception as e:
        warnings.warn(f"getattr({obj!r}, {attr_name!r}, {default!r}) raised an exception: {e!r}")
        return default


def get_allattr(obj: Any) -> Any:
    """
    Get __all__ attribute of the module.
    Return None if given *obj* does not have __all__.
    Raises ValueError if given *obj* have invalid __all__.
    reference: sphinx
    """
    __all__ = safe_getattr(obj, '__all__', None)
    if __all__ is None:
        return None
    else:
        if isinstance(__all__, (list, tuple)) and all(isinstance(e, str) for e in __all__):
            return __all__
        else:
            raise ValueError(__all__)
