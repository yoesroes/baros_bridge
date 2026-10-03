import openseespy.opensees as ops
from components.box_girder import BoxGirder
from components.pier_head import PierHead
from components.pier import Pier, PierSection
from components.pile_cap import PileCap
from components.bored_pile import BoredPile, SoilSpring


class Bridge:
    """
    Model jembatan 9 bentang, 2 abutmen, 8 pier.
    
    Layout:
    abut1 - P1 - P2 - P3 - P4 - P5 - P6 - P7 - P8 - abut2
    span: 9 bentang (8 span antar pier + 2 span tepi)
    """
    def __init__(self, num_span=9, num_pier=8):
        self.num_span = num_span
        self.num_pier = num_pier
        self.nodes = {}
        self.elements = {}
        self.materials = {}
        self.sections = {}
        self.components = {
            'box_girder': [],
            'pier_head': [],
            'pier': [],
            'pile_cap': [],
            'bored_pile': [],
        }

    def init_model(self, ndm=3, ndf=6):
        ops.wipe()
        ops.model('basic', '-ndm', ndm, '-ndf', ndf)

    def add_node(self, tag, coords):
        ops.node(tag, *coords)
        self.nodes[tag] = coords

    def add_material(self, material):
        material.ensure_defined()
        self.materials[material.mat_tag] = material

    def add_section(self, section):
        section.define()
        self.sections[section.sec_tag] = section

    def add_box_girder(self, bg):
        bg.define()
        self.components['box_girder'].append(bg)

    def add_pier_head(self, ph):
        ph.define()
        self.components['pier_head'].append(ph)

    def add_pier(self, pier):
        pier.define()
        self.components['pier'].append(pier)

    def add_pile_cap(self, pc):
        pc.define()
        self.components['pile_cap'].append(pc)

    def add_bored_pile(self, bp):
        bp.define()
        self.components['bored_pile'].append(bp)

    def define_geom_transf(self, transf_tag=1, type='Linear',
                           vecxz=(1, 0, 0)):
        ops.geomTransf(type, transf_tag, *vecxz)

    def apply_supports(self, node_tag, fixity):
        """fixity: [ux, uy, uz, rx, ry, rz]"""
        ops.fix(node_tag, *fixity)