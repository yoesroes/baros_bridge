class BoxGirder:
    """
    Box Girder - biasanya dimodelkan sebagai elemen elasticBeamColumn
    atau fiber section jika butuh nonlinear.
    
    Parameter:
    ----------
    tag : int
        tag elemen box girder
    i_node, j_node : int
        node ujung-ujung elemen
    A : float
        luas penampang (m^2)
    E : float
        modulus elastisitas (kPa)
    G : float
        modulus geser (kPa)
    J : float
        konstanta torsi (m^4)
    Iy, Iz : float
        momen inersia (m^4)
    transf_tag : int
        tag transformasi geometri
    """
    def __init__(self, tag, i_node, j_node, A, E, G, J, Iy, Iz,
                 transf_tag=1, mass=0.0, geom_transf='Linear'):
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
        self.mass = mass
        self.geom_transf = geom_transf

    def define(self):
        import openseespy.opensees as ops
        ops.element('elasticBeamColumn',
                    self.tag, self.i_node, self.j_node,
                    self.A, self.E, self.G, self.J, self.Iy, self.Iz,
                    self.transf_tag)

    def set_mass(self, node_i, node_j):
        """Assign massa terdistribusi ke node"""
        import openseespy.opensees as ops
        if self.mass > 0:
            ops.mass(node_i, self.mass/2, self.mass/2, 0.0)
            ops.mass(node_j, self.mass/2, self.mass/2, 0.0)


class BoxGirderFiber:
    """
    Versi fiber section untuk box girder (analisis nonlinear).
    """
    def __init__(self, tag, i_node, j_node, section_tag,
                 transf_tag=1, num_int_pts=5):
        self.tag = tag
        self.i_node = i_node
        self.j_node = j_node
        self.section_tag = section_tag
        self.transf_tag = transf_tag
        self.num_int_pts = num_int_pts

    def define(self):
        import openseespy.opensees as ops
        ops.element('nonlinearBeamColumn',
                    self.tag, self.i_node, self.j_node,
                    self.num_int_pts, self.section_tag, self.transf_tag)