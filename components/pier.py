"""
Pier / kolom jembatan (elastic atau fiber).

Perbaikan dibanding versi sebelumnya:
- PierSection persegi: tulangan longitudinal SEKARANG ditempatkan (versi lama
  hanya menghitung n_per_side lalu berhenti, jadi penampang tanpa baja).
- Tulangan diletakkan di as bar: cover + db_hoop + db/2 dari tepi
  (versi lama menaruhnya di batas core, yaitu di tepi luar sengkang).
- Section fiber 3D diberi kekakuan torsi (-GJ). Tanpa GJ, DOF torsi
  elemen nonlinear bernilai nol dan matriks kekakuan singular.
- Elemen nonlinear memakai forceBeamColumn + beamIntegration Lobatto
  (nonlinearBeamColumn adalah nama lama).
- patch 'circ' diberi sudut awal/akhir eksplisit (0, 360).
- Validasi properti elastis; dukungan massa per panjang ('-mass').

Sumbu lokal (asumsi: y vertikal, elemen pier sejajar sumbu y, vecxz = (1,0,0)):
    x lokal = global y (naik),  y lokal = global z,  z lokal = global x.
Koordinat fiber (y, z) pada section = (global z, global x).
    b  -> arah z section (= global x, memanjang jembatan)
    h  -> arah y section (= global z, melintang jembatan)
Pastikan b dan h cocok dengan arah lebar/tinggi pier sebenarnya.

Unit: kN, m, kPa.
"""

import math
import warnings

import openseespy.opensees as ops

try:
    from core.rebar_layout import RebarLayout
except ImportError:                     # dijalankan dari folder core/
    from rebar_layout import RebarLayout


class Pier:
    """
    Pier / kolom jembatan.

    Parameter:
    ----------
    tag : int
        tag elemen pier
    i_node, j_node : int
        node bawah (pile cap) dan atas (pier head)
    A, E, G, J, Iy, Iz : float
        properti elastis (wajib bila nonlinear=False)
    section_tag : int
        tag fiber section (wajib bila nonlinear=True)
    transf_tag : int
        tag geomTransf (disarankan transformasi khusus pier, mis. 'PDelta')
    num_int_pts : int
        jumlah integration points (Lobatto)
    nonlinear : bool
        True = fiber section (forceBeamColumn), False = elastic
    integration_tag : int, optional
        tag beamIntegration. Default = tag elemen.
    mass_per_length : float
        massa per panjang (ton/m = kN.s2/m2). 0 = tanpa massa.
    """

    def __init__(self, tag, i_node, j_node,
                 A=None, E=None, G=None, J=None, Iy=None, Iz=None,
                 section_tag=None, transf_tag=1,
                 num_int_pts=5, nonlinear=False,
                 integration_tag=None, mass_per_length=0.0):
        self.tag = tag
        self.i_node = i_node
        self.j_node = j_node
        self.A = A
        self.E = E
        self.G = G
        self.J = J
        self.Iy = Iy
        self.Iz = Iz
        self.section_tag = section_tag
        self.transf_tag = transf_tag
        self.num_int_pts = num_int_pts
        self.nonlinear = nonlinear
        self.integration_tag = integration_tag
        self.mass_per_length = mass_per_length

    def define(self):
        extra = ['-mass', self.mass_per_length] if self.mass_per_length > 0 \
            else []

        if self.nonlinear:
            if self.section_tag is None:
                raise ValueError("Pier {}: section_tag wajib untuk "
                                 "nonlinear=True.".format(self.tag))
            int_tag = (self.integration_tag
                       if self.integration_tag is not None else self.tag)
            ops.beamIntegration('Lobatto', int_tag,
                                self.section_tag, self.num_int_pts)
            ops.element('forceBeamColumn',
                        self.tag, self.i_node, self.j_node,
                        self.transf_tag, int_tag, *extra)
        else:
            nama = ['A', 'E', 'G', 'J', 'Iy', 'Iz']
            kosong = [n for n in nama if getattr(self, n) is None]
            if kosong:
                raise ValueError("Pier {}: properti elastis belum diisi: "
                                 "{}".format(self.tag, ", ".join(kosong)))
            ops.element('elasticBeamColumn',
                        self.tag, self.i_node, self.j_node,
                        self.A, self.E, self.G, self.J,
                        self.Iy, self.Iz, self.transf_tag, *extra)


class PierSection:
    """
    Fiber section pier (circular / rectangular).

    Parameters
    ----------
    sec_tag : int
    shape : 'circular' | 'rectangular'
    dims : float (D) atau (b, h)
    cover : float
        selimut beton ke tepi luar sengkang (m)
    core_mat, cover_mat, steel_mat : int
        tag material
    n_bars : int
        jumlah tulangan longitudinal
    bar_area : float
        luas satu tulangan (m2)
    n_fiber_circ, n_fiber_rad : int
        subdivisi keliling dan radial (circular)
    n_fiber_rect : int
        subdivisi tiap arah (rectangular)
    db_hoop : float
        diameter sengkang (m), untuk posisi as tulangan
    GJ : float
        kekakuan torsi section (kN.m2). WAJIB untuk model 3D (ndf=6).
        Contoh: G*J*faktor_retak.
    n_bars_top, n_bars_bot, n_bars_side : int, optional
        distribusi tulangan persegi (lihat RebarLayout.place_rectangular).
        Semua None -> distribusi simetris otomatis.
    """

    def __init__(self, sec_tag, shape, dims, cover,
                 core_mat, cover_mat, steel_mat, n_bars, bar_area,
                 n_fiber_circ=24, n_fiber_rect=10, n_fiber_rad=8,
                 db_hoop=0.0, GJ=None,
                 n_bars_top=None, n_bars_bot=None, n_bars_side=None):
        if shape not in ('circular', 'rectangular'):
            raise ValueError("shape harus 'circular' atau 'rectangular'.")
        self.sec_tag = sec_tag
        self.shape = shape
        self.dims = dims
        self.cover = cover
        self.core_mat = core_mat
        self.cover_mat = cover_mat
        self.steel_mat = steel_mat
        self.n_bars = n_bars
        self.bar_area = bar_area
        self.n_fiber_circ = n_fiber_circ
        self.n_fiber_rad = n_fiber_rad
        self.n_fiber_rect = n_fiber_rect
        self.db_hoop = db_hoop
        self.GJ = GJ
        self.n_bars_top = n_bars_top
        self.n_bars_bot = n_bars_bot
        self.n_bars_side = n_bars_side
        self.coords = []          # koordinat tulangan (y, z) setelah define()

    # ------------------------------------------------------------------
    def bar_diameter(self):
        return math.sqrt(4.0 * self.bar_area / math.pi)

    def gross_area(self):
        if self.shape == 'circular':
            return math.pi * self.dims ** 2 / 4.0
        b, h = self.dims
        return b * h          # persegi penuh (sudut membulat tidak dihitung)

    def steel_ratio(self):
        """Rasio tulangan longitudinal terhadap luas bruto."""
        return self.n_bars * self.bar_area / self.gross_area()

    # ------------------------------------------------------------------
    def define(self):
        if self.GJ is None:
            warnings.warn(
                "PierSection {}: GJ tidak diisi. Pada model 3D (ndf=6) DOF "
                "torsi elemen fiber akan singular.".format(self.sec_tag))
            ops.section('Fiber', self.sec_tag)
        else:
            ops.section('Fiber', self.sec_tag, '-GJ', self.GJ)

        rebar = RebarLayout(self.steel_mat, self.bar_diameter(), self.n_bars)

        if self.shape == 'circular':
            D = self.dims
            R = D / 2.0
            Rc = R - self.cover
            # Core (0 .. Rc)
            ops.patch('circ', self.core_mat,
                      self.n_fiber_circ, self.n_fiber_rad,
                      0.0, 0.0, 0.0, Rc, 0.0, 360.0)
            # Cover (Rc .. R)
            ops.patch('circ', self.cover_mat,
                      self.n_fiber_circ, 2,
                      0.0, 0.0, Rc, R, 0.0, 360.0)
            self.coords = rebar.place_circular(
                radius=rebar.radius_circular(D, self.cover, self.db_hoop))
        else:
            b, h = self.dims
            yc = h / 2.0 - self.cover
            zc = b / 2.0 - self.cover
            n = self.n_fiber_rect
            # Core
            ops.patch('rect', self.core_mat, n, n, -yc, -zc, yc, zc)
            # Cover (4 sisi)
            ops.patch('rect', self.cover_mat, n, 2, -h / 2, -b / 2,
                      h / 2, -zc)
            ops.patch('rect', self.cover_mat, n, 2, -h / 2, zc,
                      h / 2, b / 2)
            ops.patch('rect', self.cover_mat, 2, n, -h / 2, -zc,
                      -yc, zc)
            ops.patch('rect', self.cover_mat, 2, n, yc, -zc,
                      h / 2, zc)
            # Tulangan longitudinal
            self.coords = rebar.place_rectangular(
                b, h, self.cover,
                n_bars_top=self.n_bars_top, n_bars_bot=self.n_bars_bot,
                n_bars_side=self.n_bars_side, db_hoop=self.db_hoop)
