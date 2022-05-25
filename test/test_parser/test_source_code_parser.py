from inspect import getsource
from typing import Dict
from VPLCodeGenerator.parser.source_code_parser import VariableParser
from test_data import module_example


class TestVariableParser:
    source = getsource(module_example)
    encoding = 'utf-8'
    annotations_expected = {('ClassA', 'attr3'): 'float',
                            ('ClassA', 'attr4'): 'str',
                            ('ClassA', 'attr5'): 'str',
                            ('ClassA.ClassC', 'attr1'): 'None',
                            ('', 'instance_of_a'): 'ClassA',
                            ('', 'var1'): 'float',
                            ('', 'var2'): 'str',
                            ('', 'var3'): 'int',
                            ('', 'var4'): 'list'}
    docstring_expected = {('ClassA', 'attr1'): 'doc comment after assignment',
                          ('ClassA', 'attr2'): 'doc comment before assignment',
                          ('ClassA', 'attr3'): 'attribute docstring',
                          ('ClassA', 'attr4'): 'attribute multiple'
                                               '\nline docstring',
                          ('ClassA', 'attr5'): 'the string followed by a attribute',
                          ('ClassA.ClassC', 'attr1'): 'nested class attributes comment',
                          ('', 'instance_of_a'): 'doc comment before assignment first line'
                                                 '\ndoc comment before assignment second line',
                          ('', 'var1'): 'doc comment after assignment',
                          ('', 'var3'): 'variable docstring',
                          ('', 'var4'): 'variable multiple'
                                        '\nline docstring',
                          ('', 'var5'): 'the string followed by a attribute',
                          }
    top_level_ns, ns_classA, ns_classC = '', 'ClassA', 'ClassA.ClassC'

    def setup_method(self):
        self.variable_parser = VariableParser(self.source, self.encoding)
        self.expected_at_top_level: Dict[str, str] = {}
        self.expected_in_classA: Dict[str, str] = {}
        self.expected_in_classC: Dict[str, str] = {}

    def test_attribute_assignment_in_init(self):
        assert self.variable_parser.code == self.source
        assert self.variable_parser.encoding == self.encoding
        assert self.variable_parser.annotations == {}
        assert self.variable_parser.docstring == {}
        assert self.variable_parser._parsed is False

    def test_parse(self):
        self.variable_parser.parse()
        assert self.variable_parser.annotations == self.annotations_expected
        assert self.variable_parser.docstring == self.docstring_expected

    def test_annotations_in_ns(self):
        for (ns, name), v in self.annotations_expected.items():
            if ns == self.top_level_ns:
                self.expected_at_top_level[name] = v
            elif ns == self.ns_classA:
                self.expected_in_classA[name] = v
            elif ns == self.ns_classC:
                self.expected_in_classC[name] = v

        assert self.variable_parser.annotations_in_ns(self.top_level_ns) == self.expected_at_top_level
        assert self.variable_parser.annotations_in_ns(self.ns_classA) == self.expected_in_classA
        assert self.variable_parser.annotations_in_ns(self.ns_classC) == self.expected_in_classC

    def test_docstring_in_ns(self):
        for (ns, name), v in self.docstring_expected.items():
            if ns == self.top_level_ns:
                self.expected_at_top_level[name] = v
            elif ns == self.ns_classA:
                self.expected_in_classA[name] = v
            elif ns == self.ns_classC:
                self.expected_in_classC[name] = v

        assert self.variable_parser.docstring_in_ns(self.top_level_ns) == self.expected_at_top_level
        assert self.variable_parser.docstring_in_ns(self.ns_classA) == self.expected_in_classA
        assert self.variable_parser.docstring_in_ns(self.ns_classC) == self.expected_in_classC
