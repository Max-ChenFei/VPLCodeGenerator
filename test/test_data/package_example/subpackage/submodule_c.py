from ..submodule_b import SubmoduleB


class SubmoduleC(SubmoduleB):
    def __init__(self, name):
        self.name = name

    def myname(self):
        return self.name
