"""
Bored Pile - beam-column elastis + pegas tanah (zeroLength).

Perbaikan dibanding versi sebelumnya:
- Arah pegas: dengan y vertikal, arah LATERAL adalah x (dir 1) dan z (dir 3).
  Versi lama memetakan 'y' ke dir 2, yang sebenarnya pegas VERTIKAL, dan
  tidak punya arah z. Sekarang mendukung 'x', 'y', 'z'.
- Tag elemen pegas tidak lagi memakai mat_tag (bentrok dengan tag elemen
  lain). Pakai sp['ele_tag'] atau otomatis tag*1000 + indeks.
- mat_tag 1-4 dicadangkan oleh materials.py; ditolak.
- tip_fixity benar-benar diterapkan (lihat is_tip).
- Validasi key pegas dan SoilSpring.define() untuk tipe tak didukung.

Unit: kN, m. k pegas (kN/m) = kh * lebar pile * panjang tributari.
"""

import openseespy.opensees as ops

RESERVED_MAT_TAGS = {1, 2, 3, 4}          # materials.MAT_TAGS
ARAH = {'x': 1, 'y': 2, 'z': 3}


class BoredPile:
    """
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
        {'node', 'gnd_node', 'k', 'mat_tag', 'direction': 'x'|'z'|'y',
         'ele_tag' (opsional)}
        gnd_node = node tanah (harus sudah dibuat dan di-fix).
    tip_fixity : str
        'fixed' atau 'free'; berlaku jika is_tip=True.
    is_tip : bool
        True bila j_node segmen ini adalah ujung bawah pile.
    """

    def __init__(self, tag, i_node, j_node,
                 A, E, G, J, Iy, Iz,
                 transf_tag=1, soil_springs=None,
                 tip_fixity='free', is_tip=False):
        if tip_fixity not in ('fixed', 'free'):
            raise ValueError("tip_fixity harus 'fixed' atau 'free'.")
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
        self.is_tip = is_tip

    def define(self):
        ops.element('elasticBeamColumn',
                    self.tag, self.i_node, self.j_node,
                    self.A, self.E, self.G, self.J,
                    self.Iy, self.Iz, self.transf_tag)

        for idx, sp in enumerate(self.soil_springs):
            for key in ('node', 'gnd_node', 'k', 'mat_tag'):
                if key not in sp:
                    raise KeyError("soil_springs[{}] belum punya '{}'."
                                   .format(idx, key))
            mat_tag = sp['mat_tag']
            if mat_tag in RESERVED_MAT_TAGS:
                raise ValueError("mat_tag {} dicadangkan materials.py."
                                 .format(mat_tag))
            arah = sp.get('direction', 'x')
            if arah not in ARAH:
                raise ValueError("direction harus salah satu dari {}."
                                 .format(list(ARAH)))
            ele_tag = sp.get('ele_tag', self.tag * 1000 + idx + 1)

            ops.uniaxialMaterial('Elastic', mat_tag, sp['k'])
            ops.element('zeroLength', ele_tag, sp['node'], sp['gnd_node'],
                        '-mat', mat_tag, '-dir', ARAH[arah])

        if self.is_tip and self.tip_fixity == 'fixed':
            ops.fix(self.j_node, 1, 1, 1, 1, 1, 1)


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
        if self.type == 'Elastic':
            ops.uniaxialMaterial('Elastic', self.mat_tag, self.k_initial)
        else:
            raise NotImplementedError(
                "Tipe '{}' belum didukung (tambahkan PySimple1 / "
                "HyperbolicGapMaterial).".format(self.type))
