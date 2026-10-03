class BoredPile:
    """
    Bored Pile - dimodelkan dengan elemen beam-column dan
    tumpuan spring di sepanjang kedalaman (p-y curve).
    
    Parameter:
    ----------
    tag : int
        tag elemen pile
    i_node, j_node : int
        node atas dan bawah segmen pile
    A, E, G, J, Iy, Iz : float
        properti section
    transf_tag : int
    soil_springs : list of dict
        list of {'node': int, 'k': float, 'direction': 'x'/'y'}
        untuk tumpuan lateral (p-y curve)
    tip_fixity : str
        'fixed' atau 'free' untuk ujung bawah
    """
    def __init__(self, tag, i_node, j_node,
                 A, E, G, J, Iy, Iz,
                 transf_tag=1, soil_springs=None,
                 tip_fixity='free'):
        self.tag = tag
        self.i_node = i_node
        self.j_node = j_node
        self.A = A
        self.E = E
        self.G = G
        self.J = J
        self.Iy = Iy
        self.Iz = Iz
        self.transf_tag = transf_tag
        self.soil_springs = soil_springs if soil_springs else []
        self.tip_fixity = tip_fixity

    def define(self):
        import openseespy.opensees as ops
        # Elemen pile
        ops.element('elasticBeamColumn',
                    self.tag, self.i_node, self.j_node,
                    self.A, self.E, self.G, self.J,
                    self.Iy, self.Iz, self.transf_tag)

        # Soil springs (p-y curve)
        for sp in self.soil_springs:
            mat_tag = sp['mat_tag']
            node = sp['node']
            k = sp['k']
            direction = sp.get('direction', 'x')
            ops.uniaxialMaterial('Elastic', mat_tag, k)
            if direction == 'x':
                ops.element('zeroLength', mat_tag, node, sp['gnd_node'],
                            '-mat', mat_tag, '-dir', 1)
            elif direction == 'y':
                ops.element('zeroLength', mat_tag, node, sp['gnd_node'],
                            '-mat', mat_tag, '-dir', 2)


class SoilSpring:
    """
    p-y curve sederhana (bisa diganti dengan API/Matlock).
    """
    def __init__(self, mat_tag, k_initial, p_ult=None, type='Elastic'):
        self.mat_tag = mat_tag
        self.k_initial = k_initial
        self.p_ult = p_ult
        self.type = type

    def define(self):
        import openseespy.opensees as ops
        if self.type == 'Elastic':
            ops.uniaxialMaterial('Elastic', self.mat_tag, self.k_initial)
        # Bisa ditambah HyperbolicGapMaterial, PySimple1, dsb.