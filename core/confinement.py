"""
ConfinementModel - Model kekangan beton berdasarkan:
    Mander, J.B., Priestley, M.J.N., Park, R. (1988).
    "Theoretical Stress-Strain Model for Confined Concrete."
    Journal of Structural Engineering, ASCE, 114(8), 1804-1826.

Mendukung:
- Circular section (spiral / circular hoop)
- Rectangular section (rectangular hoop + cross ties)
- Perhitungan f'cc, εc0, εcu, dan kurva tegangan-regangan penuh
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
            # ACI 318: Ec = 4700 * sqrt(f'c) [MPa]
            fc_MPa = self.fpc / 1000.0
            self.Ec = 4700.0 * math.sqrt(fc_MPa) * 1000.0  # kPa
        else:
            self.Ec = Ec

    # ==================================================================
    # CIRCULAR SECTION
    # ==================================================================
    def circular(self, D, cover, db_long, db_hoop, s,
                 n_hoop_bars=1, rho_cc=None):
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
            Spasi sengkang spiral/hoop (m).
        n_hoop_bars : int
            Jumlah bar sengkang pada penampang melintang (=1 untuk spiral).
        rho_cc : float, optional
            Rasio tulangan longitudinal terhadap luas core.
            Jika None, hanya confinement effect yang dihitung.

        Returns
        -------
        dict dengan keys: fcc, epsc0, epcu, fl, ke, rho_s, ...
        """
        # Diameter core (ke tengah sengkang)
        Dc = D - 2.0 * cover - db_hoop
        Ac = math.pi * Dc ** 2 / 4.0
        Acc = Ac  # circular: Ac = Acc

        # Rasio volumetrik sengkang
        # Asp = luas 1 bar sengkang
        Asp = math.pi * db_hoop ** 2 / 4.0
        rho_s = 4.0 * Asp * n_hoop_bars / (Dc * s)

        # Confinement effectiveness coefficient
        # ke = (1 - s'/(2*Dc)) / (1 - rho_cc)   ; s' = clear spacing
        s_prime = s - db_hoop
        rho_cc_val = rho_cc if rho_cc is not None else 0.0
        if rho_cc_val >= 1.0:
            rho_cc_val = 0.0
        ke = (1.0 - s_prime / (2.0 * Dc)) / (1.0 - rho_cc_val)

        # Effective lateral confining pressure
        fl = 0.5 * ke * rho_s * self.fyh   # kPa

        # Confined strength
        fcc = self._fcc_from_fl(fl)

        # Strains
        epsc0 = self._epsc0(fcc)
        epcu = self._epcu(fcc, rho_s)

        return {
            'section': 'circular',
            'D': D, 'Dc': Dc, 'Ac': Ac, 'Acc': Acc,
            'rho_s': rho_s, 'ke': ke, 'fl': fl,
            'fcc': fcc, 'epsc0': epsc0, 'epcu': epcu,
            'Ec': self.Ec,
            'fpc': self.fpc,
        }

    # ==================================================================
    # RECTANGULAR SECTION
    # ==================================================================
    def rectangular(self, bx, hy, cover, db_long, db_hoop,
                    sx, sy, n_x=2, n_y=2, rho_cc=None):
        """
        Hitung parameter kekangan untuk penampang persegi.

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
        sx : float
            Spasi sengkang arah-x (m).
        sy : float
            Spasi sengkang arah-y (m).
        n_x : int
            Jumlah area tulangan longitudinal yang ditahan di sisi-x.
        n_y : int
            Jumlah area tulangan longitudinal yang ditahan di sisi-y.
        rho_cc : float, optional
            Rasio tulangan longitudinal terhadap luas core.

        Returns
        -------
        dict dengan keys: fcc_x, fcc_y, fcc, epsc0, epcu, ...
        """
        # Dimensi core (ke tengah sengkang)
        bc = bx - 2.0 * cover - db_hoop
        hc = hy - 2.0 * cover - db_hoop
        Ac = bc * hc
        Acc = Ac

        # Luas 1 bar sengkang
        Asp = math.pi * db_hoop ** 2 / 4.0

        # Rasio volumetrik sengkang
        rho_x = Asp * n_x / (bc * sx)   # sumbu-x
        rho_y = Asp * n_y / (hc * sy)   # sumbu-y

        # Effective confinement coefficient (sama untuk kedua arah)
        rho_cc_val = rho_cc if rho_cc is not None else 0.0
        if rho_cc_val >= 1.0:
            rho_cc_val = 0.0

        # Arah-x
        sx_prime = sx - db_hoop
        ke_x = (1.0 - sx_prime / (2.0 * bc)) / (1.0 - rho_cc_val)

        # Arah-y
        sy_prime = sy - db_hoop
        ke_y = (1.0 - sy_prime / (2.0 * hc)) / (1.0 - rho_cc_val)

        flx = ke_x * rho_x * self.fyh
        fly = ke_y * rho_y * self.fyh

        # Equivalent uniform pressure
        fl = math.sqrt(flx * fly) if (flx > 0 and fly > 0) else 0.0

        # Confined strength
        fcc = self._fcc_from_fl(fl)

        # Strains
        epsc0 = self._epsc0(fcc)

        # εcu untuk rectangular (Mander Eq. 33)
        # εcu = 0.004 + 1.4 * rho_s * fyh * esm / fcc
        # di sini rho_s = rata-rata volumetrik = 0.5*(rho_x + rho_y)
        rho_s = 0.5 * (rho_x + rho_y)
        epcu = self._epcu(fcc, rho_s)

        return {
            'section': 'rectangular',
            'bx': bx, 'hy': hy, 'bc': bc, 'hc': hc,
            'Ac': Ac, 'Acc': Acc,
            'rho_x': rho_x, 'rho_y': rho_y, 'rho_s': rho_s,
            'ke_x': ke_x, 'ke_y': ke_y,
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
        """
        Mander Eq. 11: εc0 = 0.002 * [1 + 5*(f'cc/f'c - 1)]
        """
        return 0.002 * (1.0 + 5.0 * (fcc / self.fpc - 1.0))

    def _epcu(self, fcc, rho_s):
        """
        Mander Eq. 33: εcu = 0.004 + 1.4 * rho_s * fyh * esm / f'cc
        """
        return 0.004 + 1.4 * rho_s * self.fyh * self.esm / fcc

    # ==================================================================
    # STRESS-STRAIN CURVE
    # ==================================================================
    def stress(self, eps, fcc, epsc0, Ec=None):
        """
        Mander Eq. 1 & 4: tegangan beton terkekang pada regangan eps.

        σc = f'cc * x * r / (r - 1 + x^r)
        x = εc / εc0
        r = Ec / (Ec - Esec)
        Esec = f'cc / εc0
        """
        Ec = Ec or self.Ec
        Esec = fcc / epsc0
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
        print(f"  ke       = {result.get('ke', result.get('ke_x', 0)):8.3f}")
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

    Digunakan bersama ManderConfinement untuk langsung menghasilkan
    uniaxialMaterial OpenSees.

    Catatan:
    - Cover  : Concrete02 (model Kent-Scott-Park dimodifikasi)
    - Core   : Concrete04 (Popovics + Mander, siap untuk fiber)
    """

    def __init__(self, fpc, epsc0_unconf=-0.002, fpcu_unconf=None,
                 epsU_unconf=-0.005, ft=None, Ets=None):
        """
        Parameter cover (tak terkekang).
        fpc : kuat tekan (kPa, nilai POSITIF).
        """
        self.fpc = abs(fpc)
        self.epsc0 = epsc0_unconf
        self.fpcu = fpcu_unconf if fpcu_unconf else -0.2 * self.fpc
        self.epsU = epsU_unconf
        self.ft = ft if ft else 0.1 * self.fpc     # tensile strength
        self.Ets = Ets if Ets else 0.05 * self._Ec()

    def _Ec(self):
        return 4700.0 * math.sqrt(self.fpc / 1000.0) * 1000.0  # kPa

    def define_cover(self, mat_tag):
        """Definisikan material cover (Concrete02)."""
        ops.uniaxialMaterial(
            'Concrete02', mat_tag,
            -self.fpc,        # f'c (negatif untuk tekan)
            self.epsc0,
            -self.fpcu,       # fpcu (negatif)
            self.epsU,
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
            -epsc0,           # εc0 (negatif)
            -epcu,            # εcu (negatif)
            Ec,
            self.ft
        )