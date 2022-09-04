"""
    This parser extract definition of variable, functions, class and modueles from reStructuredText files.
    In reST, each level of table of content is regarded as a module in Python
    Reference:
    https://docutils.sourceforge.io/rst.html
    https://www.sphinx-doc.org/en/master/extdev/nodes.html#sphinx.addnodes.desc_parameter
"""
import pickle
import shutil
import tempfile
from os import path

import sphinx.addnodes as SphinxNodeTypes
from sphinx.application import ENV_PICKLE_FILENAME
from sphinx.cmd.build import build_main
from sphinx.environment import BuildEnvironment

from VPLCodeGenerator.analyser import Module, Class, Function, Variable
from VPLCodeGenerator.inspect_util import is_constant
from ..parser import Parser
from ..parser import ParserSuit


class ReSTParserSuit(ParserSuit):
    def __init__(self, /, sourcedir_or_env: str | BuildEnvironment):
        self.parser_types = {'default': ReSTParser}
        if type(sourcedir_or_env) == BuildEnvironment:
            self.env = sourcedir_or_env
        else:
            self.output_dir = tempfile.mkdtemp()
            self.env = self.env_after_sphinx_build(sourcedir_or_env, self.output_dir)
        self.import_pkg_cache = {}

    def __del__(self):
        if hasattr(self, 'output_dir'):
            shutil.rmtree(self.output_dir, ignore_errors=True)

    def env_after_sphinx_build(self, source_dir, output_dir):
        doctree_dir = path.join(output_dir, '.doctrees')
        build_main(['-b', 'html', source_dir, output_dir, '-d', doctree_dir])
        with open(path.join(source_dir, ENV_PICKLE_FILENAME), 'rb') as f:
            return pickle.load(f)

    @staticmethod
    def name():
        return 'reST'

    @property
    def doctreedir(self):
        return self.env.doctreedir

    def toctree(self, name):
        if name not in self.env.toctree_includes.keys():
            return ''
        return self.env.toctree_includes[name]

    def find_title(self, name):
        if self.env:
            return self.env.titles[name].astext()


class ReSTParser(Parser):
    def __init__(self, reST_path: str = 'index', parser_suit: ReSTParserSuit = None):
        self.reST_path = reST_path
        self.parser_suit = parser_suit

    def __eq__(self, other):
        if type(other) != ReSTParser:
            return False
        return self.reST_path == other.reST_path and self.parser_suit == other.parser_suit

    def members(self):
        return self._get_members_from_rst(path.join(self.parser_suit.doctreedir, f"{self.reST_path}.doctree"))

    def _get_members_from_rst(self, reST_path):
        with open(reST_path, 'rb') as f:
            sphinx_doc = pickle.load(f)
            desc_nodes = []
            self._get_desc(sphinx_doc, desc_nodes)
            members = {}
            for desc in desc_nodes:
                members.update(self.desc2model(desc))
            return members

    def _get_desc(self, sphinx_node, desc_nodes):
        if type(sphinx_node) == SphinxNodeTypes.desc:
            desc_nodes.append(sphinx_node)
            return
        for child in sphinx_node.children:
            self._get_desc(child, desc_nodes)

    def desc2model(self, desc: SphinxNodeTypes.desc):
        objtype = desc.attributes['objtype']
        members = {}
        for child in desc.children:
            if type(child) == SphinxNodeTypes.desc_signature:
                m = self.desc_sign2model(objtype, child)
                members[m.fullname] = m
        return members

    def desc_sign2model(self, objtype, desc_sig):
        if objtype == 'class':
            return self.desc_sig2class(desc_sig)
        elif objtype == 'function' or objtype == 'method':
            return self.desc_sig2func(desc_sig)
        elif objtype == 'attribute' or objtype == 'data':
            return self.desc_sig2variable(desc_sig)

    def desc_sig2class(self, s: SphinxNodeTypes.desc_signature):
        modulename, qualname, obj = self.get_python_obj_from_node(s)
        return Class(modulename, qualname, obj, (modulename, qualname))

    def desc_sig2func(self, s: SphinxNodeTypes.desc_signature):
        modulename, qualname, obj = self.get_python_obj_from_node(s)
        return Function(modulename, qualname, obj, (modulename, qualname))

    def desc_sig2variable(self, s: SphinxNodeTypes.desc_signature):
        modulename, qualname, obj = self.get_python_obj_from_node(s)
        is_const = is_constant(qualname.split('.')[-1])
        return Variable(modulename, qualname, docstring='', taken_from=(modulename, qualname), default_value=obj,
                        is_const=is_const)

    def get_python_obj_from_node(self, s):
        modulename = s.attributes['module']
        qualname = s.attributes['fullname']
        module = None
        if modulename not in self.parser_suit.import_pkg_cache.keys():
            try:
                module = __import__(modulename)
            except:
                print(f"Can not import {modulename}")
            else:
                self.parser_suit.import_pkg_cache[modulename] = module
        else:
            module = self.parser_suit.import_pkg_cache[modulename]
        obj = self.get_obj_from_str(module, qualname)
        return modulename, qualname, obj

    def get_obj_from_str(self, module, qualname):
        obj = module
        for name in qualname.split('.'):
            obj = getattr(obj, name)
        return obj

    def submodules(self):
        paths = self.parser_suit.toctree(self.reST_path)
        submodules = []
        for p in paths:
            parser = self.parser_suit['module'](p, self.parser_suit)
            title = self.parser_suit.find_title(p)
            a = Module('', title, None, (), parser)
            submodules.append(a)
        return submodules
