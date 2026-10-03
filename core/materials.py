import openseespy.opensees as ops

class Material:
    """Base class untuk material"""
    def __init__(self, mat_tag, name):
        self.mat_tag = mat_tag
        self.name = name
        self._defined = False

    def define(self):
        raise NotImplementedError

    def ensure_defined(self):
        if not self._defined:
            self.define()
            self._defined = True


class ConcreteMaterial(Material):
    """Concrete01/02 untuk beton (uniaxial)"""
    def __init__(self, mat_tag, name, fpc, epsc0=None, fpcu=None, epsU=None,
                 type='Concrete01', ft=None, Ets=None):
        super().__init__(mat_tag, name)
        self.fpc = fpc          # compressive strength (negatif)
        self.epsc0 = epsc0 if epsc0 else -0.002
        self.fpcu = fpcu if fpcu else 0.0
        self.epsU = epsU if epsU else -0.005
        self.type = type
        self.ft = ft
        self.Ets = Ets

    def define(self):
        if self.type == 'Concrete01':
            ops.uniaxialMaterial('Concrete01', self.mat_tag,
                                 self.fpc, self.epsc0, self.fpcu, self.epsU)
        elif self.type == 'Concrete02':
            ops.uniaxialMaterial('Concrete02', self.mat_tag,
                                 self.fpc, self.epsc0, self.fpcu, self.epsU,
                                 self.ft, self.Ets)


class SteelMaterial(Material):
    """Steel01 untuk tulangan / baja"""
    def __init__(self, mat_tag, name, Fy, E0, b=0.01, type='Steel01'):
        super().__init__(mat_tag, name)
        self.Fy = Fy
        self.E0 = E0
        self.b = b
        self.type = type

    def define(self):
        if self.type == 'Steel01':
            ops.uniaxialMaterial('Steel01', self.mat_tag,
                                 self.Fy, self.E0, self.b)
        elif self.type == 'Steel02':
            ops.uniaxialMaterial('Steel02', self.mat_tag,
                                 self.Fy, self.E0, self.b)


class ElasticMaterial(Material):
    """Material elastis sederhana"""
    def __init__(self, mat_tag, name, E):
        super().__init__(mat_tag, name)
        self.E = E

    def define(self):
        ops.uniaxialMaterial('Elastic', self.mat_tag, self.E)