"""
Box Girder - elasticBeamColumn (atau fiber untuk analisis nonlinear).

Perbaikan dibanding versi sebelumnya:
- set_mass() lama memanggil ops.mass dengan 3 nilai (model 3D ndf=6 butuh 6)
  dan menimpa massa node bersama antar elemen. Diganti massa per panjang
  lewat opsi '-mass' elemen (terakumulasi otomatis di node).
- Parameter geom_transf yang tidak dipakai dihapus.
- from_props(): konversi properti penampang (A, Ix, Iy, J) ke argumen
  OpenSees dengan pemetaan sumbu yang benar.
- BoxGirderFiber memakai forceBeamColumn + Lobatto.

Pemetaan sumbu (asumsi: y vertikal, deck sepanjang x, vecxz = (0,0,1)):
    x lokal = global x, y lokal = global y (vertikal), z lokal = global z.
    Lentur vertikal (bidang x-y) berputar terhadap sumbu z lokal -> Iz.
    Lentur horizontal (bidang x-z) -> Iy.
Properti dari sectionproperties / README:
    Ix (sumbu horizontal penampang, ~1.45 m4)  -> Iz OpenSees
    Iy (sumbu vertikal penampang,   ~33 m4)    -> Iy OpenSees
Unit: kN, m, kPa. Massa: ton (kN.s2/m).
"""

import openseespy.opensees as ops


class BoxGirder:
    """
    Parameter:
    ----------
    tag : int
        tag elemen
    i_node, j_node : int
        node ujung
    A : float
        luas penampang (m2)
    E, G : float
        modulus elastisitas dan geser (kPa)
    J : float
        konstanta torsi (m4)
    Iy, Iz : float
        inersia sumbu lokal y dan z (m4); Iz = lentur vertikal.
    transf_tag : int
        tag geomTransf untuk elemen sejajar sumbu x
        (vecxz tidak boleh sejajar x; mis. (0, 0, 1))
    mass_per_length : float
        massa per panjang (ton/m) = w / g. 0 = tanpa massa.
    """

    def __init__(self, tag, i_node, j_node, A, E, G, J, Iy, Iz,
                 transf_tag=1, mass_per_length=0.0):
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
        self.mass_per_length = mass_per_length

    @classmethod
    def from_props(cls, tag, i_node, j_node, props, E, G,
                   transf_tag=1, mass_per_length=0.0):
        """
        Buat dari dict properti {A, Ix, Iy, J} (hasil sectionproperties).
        Ix -> Iz (lentur vertikal), Iy -> Iy (lentur horizontal).
        """
        for k in ("A", "Ix", "Iy", "J"):
            if k not in props:
                raise KeyError("props['{}'] belum ada (J perlu dihitung "
                               "dengan sec.calculate_warping_properties())."
                               .format(k))
        return cls(tag, i_node, j_node, props["A"], E, G, props["J"],
                   Iy=props["Iy"], Iz=props["Ix"],
                   transf_tag=transf_tag, mass_per_length=mass_per_length)

    def define(self):
        extra = ['-mass', self.mass_per_length] if self.mass_per_length > 0 \
            else []
        ops.element('elasticBeamColumn',
                    self.tag, self.i_node, self.j_node,
                    self.A, self.E, self.G, self.J, self.Iy, self.Iz,
                    self.transf_tag, *extra)


class BoxGirderFiber:
    """
    Versi fiber section untuk box girder (analisis nonlinear).
    Section fiber 3D harus dibuat dengan '-GJ' (lihat PierSection).
    """

    def __init__(self, tag, i_node, j_node, section_tag,
                 transf_tag=1, num_int_pts=5, integration_tag=None,
                 mass_per_length=0.0):
        self.tag = tag
        self.i_node = i_node
        self.j_node = j_node
        self.section_tag = section_tag
        self.transf_tag = transf_tag
        self.num_int_pts = num_int_pts
        self.integration_tag = integration_tag
        self.mass_per_length = mass_per_length

    def define(self):
        int_tag = (self.integration_tag
                   if self.integration_tag is not None else self.tag)
        extra = ['-mass', self.mass_per_length] if self.mass_per_length > 0 \
            else []
        ops.beamIntegration('Lobatto', int_tag,
                            self.section_tag, self.num_int_pts)
        ops.element('forceBeamColumn',
                    self.tag, self.i_node, self.j_node,
                    self.transf_tag, int_tag, *extra)
