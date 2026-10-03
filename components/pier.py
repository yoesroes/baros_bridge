class Pier:
    """
    Pier / kolom jembatan.
    
    Parameter:
    ----------
    tag : int
        tag elemen pier
    i_node, j_node : int
        node bawah (pile cap) dan atas (pier head)
    section_tag : int
        tag fiber section (untuk nonlinearBeamColumn)
    transf_tag : int
        tag geomTransf
    num_int_pts : int
        jumlah integration points
    nonlinear : bool
        True = fiber section, False = elastic
    """
    def __init__(self, tag, i_node, j_node,
                 A=None, E=None, G=None, J=None, Iy=None, Iz=None,
                 section_tag=None, transf_tag=1,
                 num_int_pts=5, nonlinear=False):
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

    def define(self):
        import openseespy.opensees as ops
        if self.nonlinear:
            ops.element('nonlinearBeamColumn',
                        self.tag, self.i_node, self.j_node,
                        self.num_int_pts, self.section_tag, self.transf_tag)
        else:
            ops.element('elasticBeamColumn',
                        self.tag, self.i_node, self.j_node,
                        self.A, self.E, self.G, self.J,
                        self.Iy, self.Iz, self.transf_tag)


class PierSection:
    """
    Section untuk pier (circular / rectangular) - fiber section.
    """
    def __init__(self, sec_tag, shape, dims, cover,
                 core_mat, cover_mat, steel_mat, n_bars, bar_area,
                 n_fiber_circ=8, n_fiber_rect=10):
        self.sec_tag = sec_tag
        self.shape = shape          # 'circular' atau 'rectangular'
        self.dims = dims            # D atau (b, h)
        self.cover = cover
        self.core_mat = core_mat
        self.cover_mat = cover_mat
        self.steel_mat = steel_mat
        self.n_bars = n_bars
        self.bar_area = bar_area
        self.n_fiber_circ = n_fiber_circ
        self.n_fiber_rect = n_fiber_rect

    def define(self):
        import openseespy.opensees as ops
        ops.section('Fiber', self.sec_tag)

        if self.shape == 'circular':
            D = self.dims
            R = D / 2.0
            Rc = R - self.cover
            # Core
            ops.patch('circ', self.core_mat, self.n_fiber_circ,
                      self.n_fiber_circ, 0.0, 0.0, 0.0, Rc)
            # Cover
            ops.patch('circ', self.cover_mat, self.n_fiber_circ,
                      self.n_fiber_circ, 0.0, 0.0, Rc, R)
            # Longitudinal bars
            import math
            for i in range(self.n_bars):
                theta = 2 * math.pi * i / self.n_bars
                y = Rc * math.sin(theta)
                z = Rc * math.cos(theta)
                ops.fiber(y, z, self.bar_area, self.steel_mat)
        else:  # rectangular
            b, h = self.dims
            yc = h/2 - self.cover
            zc = b/2 - self.cover
            # Core
            ops.patch('rect', self.core_mat,
                      self.n_fiber_rect, self.n_fiber_rect,
                      -yc, -zc, yc, zc)
            # Cover (4 sisi)
            ops.patch('rect', self.cover_mat,
                      self.n_fiber_rect, 2,
                      -h/2, -b/2, h/2, -zc)
            ops.patch('rect', self.cover_mat,
                      self.n_fiber_rect, 2,
                      -h/2, zc, h/2, b/2)
            ops.patch('rect', self.cover_mat,
                      2, self.n_fiber_rect,
                      -h/2, -zc, -yc, zc)
            ops.patch('rect', self.cover_mat,
                      2, self.n_fiber_rect,
                      yc, -zc, h/2, zc)
            # Bars di 4 sisi
            import numpy as np
            n_per_side = self.n_bars // 4
            # implementasi bars sesuai kebutuhan