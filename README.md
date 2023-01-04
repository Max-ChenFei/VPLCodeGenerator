# VPLCodeGenerator
##  Questions?
* offline generation
* realtime generation

[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3104/)
[![test](https://github.com/Max-ChenFei/VPLCodeGenerator/actions/workflows/test.yml/badge.svg)](https://github.com/Max-ChenFei/VPLCodeGenerator/actions/workflows/test.yml)

Visual Programming Language Elements Auto-Generation

## Development
### Docstring
The [NumPy style](https://numpydoc.readthedocs.io/en/latest/format.html#) docstring is used for functions, class, modules 
in this library.

`#:` doc comment is used for variable or attributes docstring. 

```python
class AClass(object):
    """    
    Description for class 

    """

    def __init__(self, v1, v2):
        self.v1 = v1 #: initial value: v1 using doc comment
        self.v2 = v2 # initial value: v2 using comment
```
