"""
ConfinementModel - Model kekangan beton berdasarkan:
    Mander, J.B., Priestley, M.J.N., Park, R. (1988).
    "Theoretical Stress-Strain Model for Confined Concrete."
    Journal of Structural Engineering, ASCE, 114(8), 1804-1826.

Mendukung:
- Circular section (spiral / circular hoop)
- Rectangular section (rectangular hoop + cross ties)
- Perhitungan f'cc, epsc0, epscu, dan kurva tegangan-regangan penuh

Perbaikan dibanding versi sebelumnya:
- ManderConcrete.define_cover: tegangan residual tidak lagi terbalik tanda
  dan parameter `lambda` (rat) Concrete02 sekarang dikirim.
- Rectangular: rho_x memakai dimensi core yang benar (rho_x = Asx/(s*dc),
  rho_y = Asy/(s*bc)); rho_s = rho_x + rho_y (bukan rata-rata);
  ke memakai rumus Mander lengkap (suku in-plane arching + kedua arah s').
- Spasi sengkang hanya satu nilai (s). sx dan sy dipertahankan sebagai
  argumen, tetapi harus sama.
- Circular: pilihan spiral / hoop (hoop memakai kuadrat faktor s').
- rho_cc dapat dihitung otomatis dari jumlah tulangan longitudinal (n_long).
- Guard pada stress() dan normalisasi tanda input.
"""

import math
import openseespy.opensees as ops


class ManderConfinement:
    """
    Model kekangan beton Mander (1988).

    Parameters
    ----------
    fpc : float
        Kuat tekan beton tak terkekang (nilai POSITIF dalam kPa).
    fyh : float
        Tegangan leleh sengkang (kPa).
    esm : float
        Regangan baja sengkang pada tegangan maksimum (default 0.09).
    Ec : float
        Modulus elastisitas beton (kPa). Jika None -> 4700*sqrt(f'c) [MPa]->kPa.
    """

    def __init__(self, fpc, fyh, esm=0.09, Ec=None):
        self.fpc = abs(fpc)
        self.fyh = fyh
        self.esm = esm
        if Ec is None:
            fc_MPa = self.fpc / 1000.0
            self.Ec = 4700.0 * math.sqrt(fc_MPa) * 1000.0  # kPa
        else:
            self.Ec = Ec

    # ------------------------------------------------------------------
    @staticmethod
    def _rho_cc(rho_cc, n_long, db_long, Ac):
        """
        Rasio tulangan longitudinal terhadap luas core.
        Prioritas: rho_cc eksplisit > dihitung dari n_long > 0.
        """
        if rho_cc is not None:
            val = rho_cc
        elif n_long is not None:
            val = n_long * math.pi * db_long ** 2 / 4.0 / Ac
        else:
            val = 0.0
        if not 0.0 <= val < 1.0:
            raise ValueError("rho_cc harus 0 <= rho_cc < 1, didapat "
                             "{:.4f}".format(val))
        return val

    # ==================================================================
    # CIRCULAR SECTION
    # ==================================================================
    def circular(self, D, cover, db_long, db_hoop, s,
                 n_hoop_bars=1, rho_cc=None, n_long=None, spiral=True):
        """
        Hitung parameter kekangan untuk penampang lingkaran.

        Parameters
        ----------
        D : float
            Diameter luar penampang (m).
        cover : float
            Selimut beton ke tepi luar sengkang (m).
        db_long : float
            Diameter tulangan longitudinal (m).
        db_hoop : float
            Diameter tulangan sengkang spiral/hoop (m).
        s : float
            Spasi sengkang spiral/hoop, as ke as (m).
        n_hoop_bars : int
            Jumlah bar sengkang pada penampang melintang (=1 untuk spiral).
        rho_cc : float, optional
            Rasio tulangan longitudinal terhadap luas core.
        n_long : int, optional
            Jumlah tulangan longitudinal. Dipakai menghitung rho_cc bila
            rho_cc tidak diberikan. Jika keduanya None -> rho_cc = 0
            (ke sedikit overestimate).
        spiral : bool
            True: spiral (faktor 1 - s'/2ds).
            False: hoop tertutup (faktor kuadrat).

        Returns
        -------
        dict dengan keys: fcc, epsc0, epcu, fl, ke, rho_s, ...
        """
        Dc = D - 2.0 * cover - db_hoop          # diameter core (as sengkang)
        if Dc <= 0:
            raise ValueError("Diameter core <= 0; cek D, cover, db_hoop.")
        Ac = math.pi * Dc ** 2 / 4.0

        Asp = math.pi * db_hoop ** 2 / 4.0
        rho_s = 4.0 * Asp * n_hoop_bars / (Dc * s)

        s_prime = s - db_hoop                   # jarak bersih
        if s_prime < 0:
            raise ValueError("Spasi s lebih kecil dari diameter sengkang.")
        rho_cc_val = self._rho_cc(rho_cc, n_long, db_long, Ac)
        Acc = Ac * (1.0 - rho_cc_val)

        faktor = 1.0 - s_prime / (2.0 * Dc)
        if not spiral:
            faktor = faktor ** 2
        ke = faktor / (1.0 - rho_cc_val)

        fl = 0.5 * ke * rho_s * self.fyh         # kPa
        fcc = self._fcc_from_fl(fl)
        epsc0 = self._epsc0(fcc)
        epcu = self._epcu(fcc, rho_s)

        return {
            'section': 'circular',
            'D': D, 'Dc': Dc, 'Ac': Ac, 'Acc': Acc,
            'rho_s': rho_s, 'rho_cc': rho_cc_val, 'ke': ke, 'fl': fl,
            'fcc': fcc, 'epsc0': epsc0, 'epcu': epcu,
            'Ec': self.Ec,
            'fpc': self.fpc,
        }

    # ==================================================================
    # RECTANGULAR SECTION
    # ==================================================================
    def rectangular(self, bx, hy, cover, db_long, db_hoop,
                    sx, sy, n_x=2, n_y=2, rho_cc=None, n_long=None,
                    w_clear=None):
        """
        Hitung parameter kekangan untuk penampang persegi (Mander 1988).

        Parameters
        ----------
        bx : float
            Lebar penampang arah-x (m).
        hy : float
            Tinggi penampang arah-y (m).
        cover : float
            Selimut beton ke tepi luar sengkang (m).
        db_long : float
            Diameter tulangan longitudinal (m).
        db_hoop : float
            Diameter tulangan sengkang (m).
        sx, sy : float
            Spasi sengkang sepanjang sumbu elemen (as ke as, m).
            Dalam model Mander hanya ada satu spasi, jadi sx harus = sy.
        n_x : int
            Jumlah kaki sengkang (hoop + cross tie) yang SEJAJAR sumbu-x.
            Sengkang tunggal = 2.
        n_y : int
            Jumlah kaki sengkang yang SEJAJAR sumbu-y. Sengkang tunggal = 2.
        rho_cc : float, optional
            Rasio tulangan longitudinal terhadap luas core.
        n_long : int, optional
            Jumlah tulangan longitudinal (dipakai bila rho_cc None).
        w_clear : sequence of float, optional
            Jarak bersih (m) antar tulangan longitudinal yang tertahan
            sengkang/cross tie, keliling core. Dipakai untuk suku
            in-plane arching: 1 - sum(w'^2)/(6*bc*dc).
            Jika None, suku tersebut diabaikan (ke sedikit overestimate).

        Returns
        -------
        dict dengan keys: fcc, flx, fly, epsc0, epcu, ke, ...

        Catatan
        -------
        f'l ekuivalen untuk f'lx != f'ly di sini disederhanakan dengan
        akar perkalian (sqrt(flx*fly)). Mander sebenarnya memakai
        permukaan keruntuhan lima-parameter (William-Warnke).
        """
        if abs(sx - sy) > 1e-9:
            raise ValueError(
                "Model Mander memakai satu spasi sengkang; sx ({}) harus "
                "sama dengan sy ({}).".format(sx, sy))
        s = sx

        bc = bx - 2.0 * cover - db_hoop          # lebar core (arah x)
        hc = hy - 2.0 * cover - db_hoop          # tinggi core (arah y) = dc
        if bc <= 0 or hc <= 0:
            raise ValueError("Dimensi core <= 0; cek bx, hy, cover.")
        Ac = bc * hc

        Asp = math.pi * db_hoop ** 2 / 4.0
        s_prime = s - db_hoop
        if s_prime < 0:
            raise ValueError("Spasi s lebih kecil dari diameter sengkang.")

        # Mander: rho_x = Asx/(s*dc), rho_y = Asy/(s*bc)
        rho_x = Asp * n_x / (s * hc)
        rho_y = Asp * n_y / (s * bc)

        rho_cc_val = self._rho_cc(rho_cc, n_long, db_long, Ac)
        Acc = Ac * (1.0 - rho_cc_val)

        # Effective confinement (satu nilai ke untuk kedua arah)
        sum_w2 = sum(w ** 2 for w in w_clear) if w_clear else 0.0
        Ae_per_Ac = ((1.0 - sum_w2 / (6.0 * bc * hc))
                     * (1.0 - s_prime / (2.0 * bc))
                     * (1.0 - s_prime / (2.0 * hc)))
        ke = Ae_per_Ac / (1.0 - rho_cc_val)

        flx = ke * rho_x * self.fyh
        fly = ke * rho_y * self.fyh
        fl = math.sqrt(flx * fly) if (flx > 0 and fly > 0) else 0.0

        fcc = self._fcc_from_fl(fl)
        epsc0 = self._epsc0(fcc)

        # Mander Eq. 33: rho_s = rho_x + rho_y
        rho_s = rho_x + rho_y
        epcu = self._epcu(fcc, rho_s)

        return {
            'section': 'rectangular',
            'bx': bx, 'hy': hy, 'bc': bc, 'hc': hc,
            'Ac': Ac, 'Acc': Acc,
            'rho_x': rho_x, 'rho_y': rho_y, 'rho_s': rho_s,
            'rho_cc': rho_cc_val,
            'ke': ke, 'ke_x': ke, 'ke_y': ke,
            'flx': flx, 'fly': fly, 'fl': fl,
            'fcc': fcc, 'epsc0': epsc0, 'epcu': epcu,
            'Ec': self.Ec,
            'fpc': self.fpc,
        }

    # ==================================================================
    # CORE FORMULAS
    # ==================================================================
    def _fcc_from_fl(self, fl):
        """
        Mander Eq. 5: f'cc = f'c * (-1.254 + 2.254*sqrt(1 + 7.94*fl/f'c)
                                    - 2*fl/f'c)
        """
        if fl <= 0:
            return self.fpc
        r = 7.94 * fl / self.fpc
        return self.fpc * (-1.254 + 2.254 * math.sqrt(1.0 + r)
                           - 2.0 * fl / self.fpc)

    def _epsc0(self, fcc):
        """Mander Eq. 11: epsc0 = 0.002 * [1 + 5*(f'cc/f'c - 1)]"""
        return 0.002 * (1.0 + 5.0 * (fcc / self.fpc - 1.0))

    def _epcu(self, fcc, rho_s):
        """Mander Eq. 33: epscu = 0.004 + 1.4 * rho_s * fyh * esm / f'cc"""
        return 0.004 + 1.4 * rho_s * self.fyh * self.esm / fcc

    # ==================================================================
    # STRESS-STRAIN CURVE
    # ==================================================================
    def stress(self, eps, fcc, epsc0, Ec=None):
        """
        Mander Eq. 1 & 4: tegangan beton terkekang pada regangan eps
        (eps dan hasil POSITIF dalam tekan).

        sigma_c = f'cc * x * r / (r - 1 + x^r)
        x = eps / epsc0 ; r = Ec / (Ec - Esec) ; Esec = f'cc / epsc0
        """
        Ec = self.Ec if Ec is None else Ec
        Esec = fcc / epsc0
        if Esec >= Ec:
            raise ValueError(
                "Esec ({:.3e}) >= Ec ({:.3e}); kurva Mander tidak "
                "terdefinisi (cek epsc0 / fcc).".format(Esec, Ec))
        r = Ec / (Ec - Esec)
        x = eps / epsc0
        return fcc * x * r / (r - 1.0 + x ** r)

    def print_summary(self, result, name="Section"):
        """Cetak ringkasan parameter kekangan."""
        print(f"\n=== {name} ({result['section']}) ===")
        print(f"  f'c      = {result['fpc']/1000:8.2f} MPa")
        print(f"  f'cc     = {result['fcc']/1000:8.2f} MPa  "
              f"(+{(result['fcc']/result['fpc']-1)*100:.1f}%)")
        print(f"  fl       = {result['fl']/1000:8.2f} MPa")
        print(f"  ke       = {result.get('ke', 0):8.3f}")
        print(f"  rho_s    = {result['rho_s']:8.4f}")
        print(f"  epsc0    = {result['epsc0']:8.5f}")
        print(f"  epcu     = {result['epcu']:8.5f}")
        print(f"  Ec       = {result['Ec']/1e6:8.2f} GPa")


# ======================================================================
# CONCRETE04 wrapper - langsung mendefinisikan material ke OpenSees
# ======================================================================
class ManderConcrete:
    """
    Wrapper yang menggabungkan cover (Concrete02) dan core (Concrete04)
    berdasarkan parameter Mander.

    Catatan:
    - Cover  : Concrete02 (model Kent-Scott-Park dimodifikasi)
    - Core   : Concrete04 (Popovics + Mander, siap untuk fiber)
    """

    def __init__(self, fpc, epsc0_unconf=-0.002, fpcu_unconf=None,
                 epsU_unconf=-0.005, ft=None, Ets=None, rat=0.1):
        """
        Parameter cover (tak terkekang). Tanda input dinormalisasi:
        tekan -> negatif, tarik -> positif, sesuai konvensi OpenSees.

        fpc : kuat tekan (kPa, nilai POSITIF).
        rat : lambda Concrete02 (rasio kemiringan unload/reload), default 0.1.
        """
        self.fpc = abs(fpc)
        self.epsc0 = -abs(epsc0_unconf)
        self.fpcu = (-abs(fpcu_unconf) if fpcu_unconf is not None
                     else -0.2 * self.fpc)
        self.epsU = -abs(epsU_unconf)
        self.ft = abs(ft) if ft is not None else 0.1 * self.fpc
        self.Ets = abs(Ets) if Ets is not None else 0.05 * self._Ec()
        self.rat = rat

    def _Ec(self):
        return 4700.0 * math.sqrt(self.fpc / 1000.0) * 1000.0  # kPa

    def define_cover(self, mat_tag):
        """Definisikan material cover (Concrete02)."""
        # Urutan OpenSees: fpc epsc0 fpcu epsU lambda ft Ets
        ops.uniaxialMaterial(
            'Concrete02', mat_tag,
            -self.fpc,        # f'c (negatif)
            self.epsc0,       # negatif
            self.fpcu,        # negatif (sudah dinormalisasi)
            self.epsU,        # negatif
            self.rat,         # lambda
            self.ft,
            self.Ets
        )

    def define_core(self, mat_tag, confinement_result):
        """
        Definisikan material core (Concrete04) dari hasil Mander.

        Parameters
        ----------
        mat_tag : int
        confinement_result : dict
            Output dari ManderConfinement.circular() / .rectangular()
        """
        fcc = confinement_result['fcc']
        epsc0 = confinement_result['epsc0']
        epcu = confinement_result['epcu']
        Ec = confinement_result['Ec']

        ops.uniaxialMaterial(
            'Concrete04', mat_tag,
            -fcc,             # f'cc (negatif)
            -epsc0,           # epsc0 (negatif)
            -epcu,            # epscu (negatif)
            Ec,
            self.ft
        )
