class PierHead:
    """
    Pier Head (pile cap atas pier) - biasanya dimodelkan sebagai
    elemen kaku (rigid) atau elemen elastic pendek.
    
    Parameter:
    ----------
    tag : int
        tag elemen
    i_node, j_node : int
        node bawah dan atas pier head
    A, E, G, J, Iy, Iz : float
        properti section
    """
    def __init__(self, tag, i_node, j_node, A, E, G, J, Iy, Iz,
                 transf_tag=1, rigid=False):
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
        self.rigid = rigid

    def define(self):
        import openseespy.opensees as ops
        if self.rigid:
            # Rigid link: constraint node j terhadap node i
            ops.rigidLink('beam', self.i_node, self.j_node)
        else:
            ops.element('elasticBeamColumn',
                        self.tag, self.i_node, self.j_node,
                        self.A, self.E, self.G, self.J,
                        self.Iy, self.Iz, self.transf_tag)