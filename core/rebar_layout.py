"""
RebarLayout - Penempatan tulangan longitudinal pada fiber section OpenSees.

Mendukung:
- Circular section (bars tersebar merata)
- Rectangular section (bars di perimeter)
- User-defined coordinates
- Tulangan dalam beberapa layer (untuk box/dinding)
"""

import math
import openseespy.opensees as ops


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
    def place_circular(self, center_y=0.0, center_z=0.0, radius=0.0,
                       start_angle=0.0):
        """
        Tempatkan tulangan merata di sepanjang lingkaran.

        Parameters
        ----------
        center_y, center_z : float
            Pusat lingkaran (biasanya 0,0).
        radius : float
            Radius penempatan tulangan (= R - cover - db/2).
        start_angle : float
            Sudut awal (radian). Default 0 (mulai dari sumbu +z).
        """
        if radius <= 0:
            raise ValueError("Radius penempatan tulangan harus > 0.")
        for i in range(self.n_bars):
            theta = start_angle + 2.0 * math.pi * i / self.n_bars
            y = center_y + radius * math.sin(theta)
            z = center_z + radius * math.cos(theta)
            ops.fiber(y, z, self.A_bar, self.steel_mat_tag)

    # ------------------------------------------------------------------
    # Rectangular section
    # ------------------------------------------------------------------
    def place_rectangular(self, b, h, cover, n_bars_top=None,
                          n_bars_bot=None, n_bars_side=None):
        """
        Tempatkan tulangan di perimeter penampang persegi.

        Skema:
        - Sisi atas: n_bars_top  (termasuk 2 sudut)
        - Sisi bawah: n_bars_bot (termasuk 2 sudut)
        - Sisi kiri & kanan: n_bars_side (TIDAK termasuk sudut)

        Total = n_bars_top + n_bars_bot + 2 * n_bars_side

        Parameters
        ----------
        b : float
            Lebar penampang (m) - arah z.
        h : float
            Tinggi penampang (m) - arah y.
        cover : float
            Tebal selimut beton (m) ke tepi luar sengkang.
        n_bars_top, n_bars_bot : int
            Jumlah bar per sisi atas/bawah.
        n_bars_side : int
            Jumlah bar di sisi kiri/kanan (tanpa sudut).
        """
        # Posisi tulangan (as bar) dari tepi
        d_edge = cover + 0.5 * self.bar_diameter
        y_top = h / 2.0 - d_edge
        y_bot = -y_top
        z_left = -b / 2.0 + d_edge
        z_right = -z_left

        # Default: distribusi merata
        if n_bars_top is None or n_bars_bot is None:
            n_per_side = max(2, self.n_bars // 4)
            n_bars_top = n_bars_top or n_per_side
            n_bars_bot = n_bars_bot or n_per_side
            n_bars_side = n_bars_side or (n_per_side - 2)

        # Sisi atas
        for i in range(n_bars_top):
            z = z_left + (z_right - z_left) * i / (n_bars_top - 1)
            ops.fiber(y_top, z, self.A_bar, self.steel_mat_tag)

        # Sisi bawah
        for i in range(n_bars_bot):
            z = z_left + (z_right - z_left) * i / (n_bars_bot - 1)
            ops.fiber(y_bot, z, self.A_bar, self.steel_mat_tag)

        # Sisi kiri & kanan (tanpa sudut)
        if n_bars_side > 0:
            for i in range(1, n_bars_side + 1):
                y = y_bot + (y_top - y_bot) * i / (n_bars_side + 1)
                ops.fiber(y, z_left, self.A_bar, self.steel_mat_tag)
                ops.fiber(y, z_right, self.A_bar, self.steel_mat_tag)

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
        """
        if len(coords) != self.n_bars:
            print(f"[Warning] Jumlah coords ({len(coords)}) "
                  f"!= n_bars ({self.n_bars})")
        for y, z in coords:
            ops.fiber(y, z, self.A_bar, self.steel_mat_tag)

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