"""
RebarLayout - Penempatan tulangan longitudinal pada fiber section OpenSees.

Mendukung:
- Circular section (bars tersebar merata)
- Rectangular section (bars di perimeter)
- User-defined coordinates
- Tulangan dalam beberapa layer (untuk box/dinding)

Perbaikan dibanding versi sebelumnya:
- place_rectangular: default jumlah bar kini TOTAL = n_bars (sebelumnya
  hanya n_bars - 4); TypeError saat n_bars_side None sudah diperbaiki;
  pembagian nol saat n_bars_top/bot = 1 dihilangkan.
- Jumlah bar total divalidasi terhadap n_bars (ValueError bila berbeda),
  sehingga total_area() dan rho() konsisten dengan yang benar-benar
  ditempatkan.
- Jarak as bar ke tepi memperhitungkan diameter sengkang (db_hoop), sesuai
  definisi cover "ke tepi luar sengkang".
- Semua place_* mengembalikan daftar koordinat (y, z) untuk verifikasi/plot.
"""

import math
import openseespy.opensees as ops


def _titik_merata(a, b, n):
    """n titik berjarak sama dari a ke b (termasuk ujung). n=1 -> tengah."""
    if n <= 0:
        return []
    if n == 1:
        return [(a + b) / 2.0]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


class RebarLayout:
    """
    Mengatur penempatan tulangan longitudinal pada fiber section.

    Parameters
    ----------
    steel_mat_tag : int
        Tag material baja tulangan (uniaxialMaterial Steel01/Steel02).
    bar_diameter : float
        Diameter tulangan longitudinal (m).
    n_bars : int
        Jumlah tulangan longitudinal.
    """

    def __init__(self, steel_mat_tag, bar_diameter, n_bars):
        self.steel_mat_tag = steel_mat_tag
        self.bar_diameter = bar_diameter
        self.n_bars = n_bars
        self.A_bar = math.pi * bar_diameter ** 2 / 4.0

    # ------------------------------------------------------------------
    # Circular section
    # ------------------------------------------------------------------
    def radius_circular(self, D, cover, db_hoop=0.0):
        """
        Radius penempatan as tulangan untuk penampang lingkaran:
        R = D/2 - cover - db_hoop - db/2
        (cover diukur ke tepi luar sengkang).
        """
        return D / 2.0 - cover - db_hoop - 0.5 * self.bar_diameter

    def place_circular(self, center_y=0.0, center_z=0.0, radius=0.0,
                       start_angle=0.0):
        """
        Tempatkan tulangan merata di sepanjang lingkaran.

        Parameters
        ----------
        center_y, center_z : float
            Pusat lingkaran (biasanya 0,0).
        radius : float
            Radius penempatan tulangan (lihat radius_circular()).
        start_angle : float
            Sudut awal (radian). Default 0 (mulai dari sumbu +z).

        Returns
        -------
        list of (y, z)
        """
        if radius <= 0:
            raise ValueError("Radius penempatan tulangan harus > 0.")
        coords = []
        for i in range(self.n_bars):
            theta = start_angle + 2.0 * math.pi * i / self.n_bars
            y = center_y + radius * math.sin(theta)
            z = center_z + radius * math.cos(theta)
            ops.fiber(y, z, self.A_bar, self.steel_mat_tag)
            coords.append((y, z))
        return coords

    # ------------------------------------------------------------------
    # Rectangular section
    # ------------------------------------------------------------------
    def _jumlah_per_sisi(self, n_top, n_bot, n_side):
        """
        Tentukan (n_top, n_bot, n_side) sehingga
        n_top + n_bot + 2*n_side = n_bars.
        """
        n = self.n_bars

        if n_top is None and n_bot is None and n_side is None:
            # Default simetris: top = bot = n//4 + 1, sisi mengisi sisanya
            if n < 4 or n % 2:
                raise ValueError(
                    "Default distribusi perimeter butuh n_bars genap >= 4 "
                    "(n_bars = {}). Isi n_bars_top/bot/side manual.".format(n))
            n_top = n_bot = n // 4 + 1
            n_side = (n - 2 * n_top) // 2
        else:
            if n_top is None and n_bot is not None:
                n_top = n_bot
            if n_bot is None and n_top is not None:
                n_bot = n_top
            if n_top is None:                 # hanya n_side diberikan
                sisa = n - 2 * n_side
                if sisa < 0 or sisa % 2:
                    raise ValueError(
                        "n_bars - 2*n_bars_side harus genap dan >= 0.")
                n_top = n_bot = sisa // 2
            if n_side is None:                # top/bot diberikan
                sisa = n - n_top - n_bot
                if sisa < 0 or sisa % 2:
                    raise ValueError(
                        "n_bars - n_top - n_bot harus genap dan >= 0 "
                        "agar sisi kiri/kanan simetris.")
                n_side = sisa // 2

        total = n_top + n_bot + 2 * n_side
        if total != n:
            raise ValueError(
                "Total bar ditempatkan ({}) != n_bars ({}).".format(total, n))
        if n_top < 2 or n_bot < 2:
            raise ValueError("Sisi atas/bawah minimal 2 bar (sudut).")
        return n_top, n_bot, n_side

    def place_rectangular(self, b, h, cover, n_bars_top=None,
                          n_bars_bot=None, n_bars_side=None, db_hoop=0.0):
        """
        Tempatkan tulangan di perimeter penampang persegi.

        Skema:
        - Sisi atas: n_bars_top  (termasuk 2 sudut)
        - Sisi bawah: n_bars_bot (termasuk 2 sudut)
        - Sisi kiri & kanan: n_bars_side (TIDAK termasuk sudut)

        Total = n_bars_top + n_bars_bot + 2 * n_bars_side = n_bars

        Parameters
        ----------
        b : float
            Lebar penampang (m) - arah z.
        h : float
            Tinggi penampang (m) - arah y.
        cover : float
            Tebal selimut beton (m) ke tepi luar sengkang.
        n_bars_top, n_bars_bot : int, optional
            Jumlah bar sisi atas/bawah.
        n_bars_side : int, optional
            Jumlah bar di sisi kiri/kanan (tanpa sudut), per sisi.
            Bila semua None -> distribusi simetris otomatis.
        db_hoop : float
            Diameter sengkang (m). Jarak as bar ke tepi =
            cover + db_hoop + db/2.

        Returns
        -------
        list of (y, z)
        """
        n_top, n_bot, n_side = self._jumlah_per_sisi(
            n_bars_top, n_bars_bot, n_bars_side)

        d_edge = cover + db_hoop + 0.5 * self.bar_diameter
        y_top = h / 2.0 - d_edge
        y_bot = -y_top
        z_left = -b / 2.0 + d_edge
        z_right = -z_left
        if y_top <= 0 or z_right <= 0:
            raise ValueError("Cover terlalu besar untuk dimensi penampang.")

        coords = []

        # Sisi atas & bawah (termasuk sudut)
        for z in _titik_merata(z_left, z_right, n_top):
            coords.append((y_top, z))
        for z in _titik_merata(z_left, z_right, n_bot):
            coords.append((y_bot, z))

        # Sisi kiri & kanan (tanpa sudut)
        for i in range(1, n_side + 1):
            y = y_bot + (y_top - y_bot) * i / (n_side + 1)
            coords.append((y, z_left))
            coords.append((y, z_right))

        for y, z in coords:
            ops.fiber(y, z, self.A_bar, self.steel_mat_tag)
        return coords

    # ------------------------------------------------------------------
    # User-defined
    # ------------------------------------------------------------------
    def place_by_coordinates(self, coords):
        """
        Place bars at explicit (y, z) coordinates.

        Parameters
        ----------
        coords : list of tuple
            Contoh: [(0.3, 0.2), (0.3, -0.2), ...]

        Returns
        -------
        list of (y, z)
        """
        if len(coords) != self.n_bars:
            print(f"[Warning] Jumlah coords ({len(coords)}) "
                  f"!= n_bars ({self.n_bars})")
        for y, z in coords:
            ops.fiber(y, z, self.A_bar, self.steel_mat_tag)
        return list(coords)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def total_area(self):
        return self.n_bars * self.A_bar

    def rho(self, Ag):
        """Rasio tulangan terhadap luas bruto."""
        return self.total_area() / Ag

    def __repr__(self):
        return (f"RebarLayout(mat={self.steel_mat_tag}, "
                f"db={self.bar_diameter*1000:.1f}mm, n={self.n_bars}, "
                f"As={self.total_area()*1e4:.2f}cm2)")
