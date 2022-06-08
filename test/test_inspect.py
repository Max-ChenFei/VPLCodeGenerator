from test_data import package_example
from VPLCodeGenerator.inspect_util import safe_getattr, get_allattr, dedent


def test_safe_getattr_when_attr_exist():
    value = safe_getattr(package_example, 'name')
    assert value == package_example.name


def test_safe_getattr_when_attr_not_exist():
    default_value = None
    value = safe_getattr(package_example, 'address', default_value)
    assert value is default_value


def test_get_allattr_when_all_attr_exist():
    value = get_allattr(package_example)
    assert value == package_example.__all__


def test_get_allattr_when_all_attr_not_exist():
    value = get_allattr(package_example.subpackage)
    assert value is None


def test_dedent():
    code = "\tclass ClassA:\n\t\ta=3\n\t\tdef attr():\n\t\t\tself.b=2"
    assert dedent(code) == 'class ClassA:\n\t\ta=3\n\t\tdef attr():\n\t\t\tself.b=2'
