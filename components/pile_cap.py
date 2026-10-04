"""
Pile Cap - elemen kaku yang menghubungkan bored pile ke pier.

Catatan: rigidLink adalah constraint multi-point. Analisis harus memakai
    ops.constraints('Transformation')   # atau 'Penalty' / 'Lagrange'
bukan 'Plain', kalau tidak constraint diabaikan/gagal.

Perbaikan: validasi properti elastis saat rigid=False; tag elemen turunan
dapat diatur (ele_tag_start) agar tidak bentrok dengan elemen lain.
"""

import openseespy.opensees as ops


class PileCap:
    """
    Parameter:
    ----------
    tag : int
        tag elemen
    master_node : int
        node master (pusat pile cap)
    slave_nodes : list of int
        node-node pile di bawah pile cap
    rigid : bool
        True: rigidLink 'beam'; False: elasticBeamColumn tebal.
    ele_tag_start : int, optional
        tag elemen pertama untuk mode non-rigid.
        Default tag*100 (elemen ke-i = start + i).
    """

    def __init__(self, tag, master_node, slave_nodes,
                 A=None, E=None, G=None, J=None, Iy=None, Iz=None,
                 transf_tag=1, rigid=True, ele_tag_start=None):
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
        self.ele_tag_start = (ele_tag_start if ele_tag_start is not None
                              else tag * 100)

    def define(self):
        if self.rigid:
            for sn in self.slave_nodes:
                ops.rigidLink('beam', self.master_node, sn)
            return

        nama = ['A', 'E', 'G', 'J', 'Iy', 'Iz']
        kosong = [n for n in nama if getattr(self, n) is None]
        if kosong:
            raise ValueError("PileCap {}: properti elastis belum diisi: {}"
                             .format(self.tag, ", ".join(kosong)))
        for i, sn in enumerate(self.slave_nodes):
            ops.element('elasticBeamColumn', self.ele_tag_start + i,
                        self.master_node, sn,
                        self.A, self.E, self.G, self.J,
                        self.Iy, self.Iz, self.transf_tag)
