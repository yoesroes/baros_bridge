class PileCap:
    """
    Pile Cap - elemen kaku yang menghubungkan bored pile ke pier.
    Biasanya dimodelkan sebagai rigid link atau elemen elastic tebal.
    
    Parameter:
    ----------
    tag : int
        tag elemen
    master_node : int
        node master (pusat pile cap)
    slave_nodes : list of int
        node-node pile di bawah pile cap
    """
    def __init__(self, tag, master_node, slave_nodes,
                 A=None, E=None, G=None, J=None, Iy=None, Iz=None,
                 transf_tag=1, rigid=True):
        self.tag = tag
        self.master_node = master_node
        self.slave_nodes = slave_nodes
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
            for sn in self.slave_nodes:
                ops.rigidLink('beam', self.master_node, sn)
        else:
            for i, sn in enumerate(self.slave_nodes):
                tag = self.tag * 100 + i
                ops.element('elasticBeamColumn', tag,
                            self.master_node, sn,
                            self.A, self.E, self.G, self.J,
                            self.Iy, self.Iz, self.transf_tag)