"""
TEST NUMERIK
5-LINE GRILLAGE vs EQUIVALENT BEAM

Tujuan:
    Sanity check respons vertikal grillage terhadap equivalent beam.

Equivalent beam:
    EI = E * Ix_total

Grillage:
    - 5 longitudinal lines
    - posisi node = nodes.Z_GARIS
    - tributary reference = section_strips.Z_GARIS_DEFAULT
    - section properties = section_strips.properti_garis()
    - transverse properties = section_strips.properti_melintang()

Catatan:
    Ini sanity check framework, bukan acceptance criterion desain.
"""

import sys
import os
import math

import openseespy.opensees as ops


# ============================================================
# PATH PROJECT
# ============================================================

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TEST_DIR)



# ============================================================
# PROJECT IMPORT
# ============================================================

from project import project_data as pdata
from core import nodes

from core import section_strips


# ============================================================
# PARAMETER TEST
# ============================================================

E = 35.0e6          # kN/m2
NU = 0.20
G = E / (2.0 * (1.0 + NU))

L = 20.0             # m
W_TOTAL = 1000.0     # kN total UDL sepanjang bentang

N_STATION = 41

REL_TOL_PASS = 0.05
REL_TOL_WARN = 0.10


# ============================================================
# SECTION
# ============================================================

SECTION_TYPE = "solid"

try:
    SECTION = pdata.BOX_SECTIONS[SECTION_TYPE]
except (AttributeError, KeyError):
    raise RuntimeError(
        "BOX_SECTIONS['{}'] tidak ditemukan di project_data.py"
        .format(SECTION_TYPE)
    )


Z_REF = tuple(section_strips.Z_GARIS_DEFAULT)

# Posisi FISIK node grillage.
# Harus sama dengan nodes.py.
Z_NODE = tuple(nodes.Z_GARIS)

N_LINE = len(Z_NODE)


# ============================================================
# HELPER
# ============================================================

def assert_close_positive(name, value):
    if value <= 0.0:
        raise RuntimeError(
            "{} harus > 0, tetapi = {}".format(name, value)
        )


def tributary_x_weights(n, length):
    """
    Bobot panjang tributary untuk node-node sepanjang bentang.

    Untuk UDL:
        ujung = dx/2
        interior = dx
        total = L
    """
    if n < 2:
        raise ValueError("Minimal 2 station diperlukan.")

    dx = length / float(n - 1)

    weights = [dx / 2.0] + \
              [dx] * (n - 2) + \
              [dx / 2.0]

    return weights


# ============================================================
# EQUIVALENT BEAM
# ============================================================

def equivalent_beam_deflection():
    """
    Defleksi maksimum balok simply supported akibat UDL.

        delta = 5 w L^4 / (384 E I)

    W_TOTAL adalah total beban sepanjang bentang:
        w = W_TOTAL / L
    """
    Ix_total = float(SECTION["Ix"])

    assert_close_positive("Ix_total", Ix_total)

    w = W_TOTAL / L

    delta = (
        5.0
        * w
        * L**4
        / (384.0 * E * Ix_total)
    )

    return delta


# ============================================================
# BUILD GRILLAGE
# ============================================================

def build_grillage():
    ops.wipe()

    ops.model(
        "basic",
        "-ndm", 3,
        "-ndf", 6
    )

    # --------------------------------------------------------
    # GEOMETRY TRANSFORM
    # Sama dengan elements.py
    # --------------------------------------------------------

    TRANSF_MEM = 1
    TRANSF_TRANS = 2

    ops.geomTransf(
        "Linear",
        TRANSF_MEM,
        0.0, 0.0, 1.0
    )

    ops.geomTransf(
        "Linear",
        TRANSF_TRANS,
        1.0, 0.0, 0.0
    )

    # --------------------------------------------------------
    # NODE
    # --------------------------------------------------------

    node = {}

    tag = 0

    for i in range(N_STATION):

        x = L * i / float(N_STATION - 1)

        for j, z in enumerate(Z_NODE):

            tag += 1

            ops.node(
                tag,
                x,
                0.0,
                z
            )

            node[(i, j)] = tag

    # --------------------------------------------------------
    # LONGITUDINAL PROPERTIES
    #
    # Sangat penting:
    #
    # properti_garis(
    #     tipe,
    #     total,
    #     z_ref,
    #     z_node
    # )
    # --------------------------------------------------------

    props_long = section_strips.properti_garis(
        SECTION_TYPE,
        SECTION,
        Z_REF,
        Z_NODE,
    )

    if len(props_long) != N_LINE:
        raise RuntimeError(
            "Jumlah properti longitudinal {} != jumlah garis {}".format(
                len(props_long),
                N_LINE,
            )
        )

    # --------------------------------------------------------
    # LONGITUDINAL ELEMENTS
    #
    # OpenSees elasticBeamColumn:
    #
    # A, E, G, J, Iy, Iz, transf
    #
    # Untuk longitudinal:
    #   p["Ix"] -> OpenSees Iz
    #
    # sama dengan elements.py.
    # --------------------------------------------------------

    ele_tag = 1

    for i in range(N_STATION - 1):

        for j in range(N_LINE):

            n1 = node[(i, j)]
            n2 = node[(i + 1, j)]

            p = props_long[j]

            ops.element(
                "elasticBeamColumn",
                ele_tag,
                n1,
                n2,
                p["A"],
                E,
                G,
                p["J"],
                p["Iy"],
                p["Ix"],
                TRANSF_MEM,
            )

            ele_tag += 1

    # --------------------------------------------------------
    # TRANSVERSE ELEMENTS
    #
    # API mengikuti elements.py:
    #
    # properti_melintang(dx, tipe, z_garis)
    #
    # z_garis = posisi fisik node.
    # --------------------------------------------------------

    for i in range(N_STATION):

        for j in range(N_LINE - 1):

            n1 = node[(i, j)]
            n2 = node[(i, j + 1)]

            dx = Z_NODE[j + 1] - Z_NODE[j]

            props_trans = section_strips.properti_melintang(
                dx,
                SECTION_TYPE,
                Z_NODE,
            )

            # Ambil property untuk segmen transverse j.
            #
            # API normalnya mengembalikan list property
            # per garis/segmen.
            if isinstance(props_trans, (list, tuple)):

                if j >= len(props_trans):
                    raise RuntimeError(
                        "Index transverse property {} di luar range {}".format(
                            j,
                            len(props_trans),
                        )
                    )

                p = props_trans[j]

            else:
                p = props_trans

            ops.element(
                "elasticBeamColumn",
                ele_tag,
                n1,
                n2,
                p["A"],
                E,
                G,
                p["J"],
                p["Iy"],
                p["Iz"],
                TRANSF_TRANS,
            )

            ele_tag += 1

    return node


# ============================================================
# LOAD + SUPPORT
# ============================================================

def apply_supports(node):
    """
    Simply supported longitudinally.

    UY = vertical
    UX = longitudinal
    UZ = transverse

    Left:
        UX UY UZ fixed

    Right:
        UX free
        UY UZ fixed

    Rotations bebas.
    """

    # --------------------------------------------------------
    # LEFT SUPPORT
    # --------------------------------------------------------

    for j in range(N_LINE):

        ops.fix(
            node[(0, j)],
            1, 1, 1,
            0, 0, 0
        )

    # --------------------------------------------------------
    # RIGHT SUPPORT
    # --------------------------------------------------------

    for j in range(N_LINE):

        ops.fix(
            node[(N_STATION - 1, j)],
            0, 1, 1,
            0, 0, 0
        )


def apply_load(node):
    """
    Total W_TOTAL didistribusikan:

    1. antar 5 longitudinal lines berdasarkan fraksi A
    2. sepanjang bentang berdasarkan tributary x

    Jumlah total harus tepat W_TOTAL.
    """

    # Fraksi transverse berdasarkan z_ref,
    # bukan z_node.
    fraksi = section_strips.fraksi_berat(
        SECTION_TYPE,
        Z_REF,
    )

    if len(fraksi) != N_LINE:
        raise RuntimeError(
            "Jumlah fraksi {} != jumlah garis {}".format(
                len(fraksi),
                N_LINE,
            )
        )

    sum_fraksi = sum(fraksi)

    if abs(sum_fraksi - 1.0) > 1.0e-10:
        raise RuntimeError(
            "Fraksi beban tidak konservatif: sum = {:.12f}".format(
                sum_fraksi
            )
        )

    x_weights = tributary_x_weights(
        N_STATION,
        L,
    )

    total_applied = 0.0

    # --------------------------------------------------------
    # LOAD PATTERN
    # --------------------------------------------------------

    ops.timeSeries(
        "Linear",
        1
    )

    ops.pattern(
        "Plain",
        1,
        1
    )

    for i in range(N_STATION):

        for j in range(N_LINE):

            P = (
                W_TOTAL
                * x_weights[i]
                / L
                * fraksi[j]
            )

            # Vertical = global Y
            ops.load(
                node[(i, j)],
                0.0,
                -P,
                0.0,
                0.0,
                0.0,
                0.0,
            )

            total_applied += P

    return total_applied


# ============================================================
# ANALYSIS
# ============================================================

def run_analysis():
    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.test(
        "NormDispIncr",
        1.0e-10,
        100,
    )
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")

    ok = ops.analyze(1)

    if ok != 0:
        raise RuntimeError(
            "Analisis grillage gagal. return code = {}".format(ok)
        )


# ============================================================
# MIDSPAN DEFLECTION
# ============================================================

def get_midspan_deflection(node):
    """
    Ambil rata-rata displacement vertikal lima longitudinal lines
    pada station tengah.
    """

    i_mid = (N_STATION - 1) // 2

    disp = []

    for j in range(N_LINE):

        tag = node[(i_mid, j)]

        uy = ops.nodeDisp(tag, 2)

        disp.append(uy)

    avg = sum(disp) / len(disp)

    return avg, disp


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print("=" * 75)
    print("EQUIVALENT BEAM SANITY TEST")
    print("=" * 75)

    print()
    print("SECTION")
    print("-" * 75)
    print("  Type       : {}".format(SECTION_TYPE))
    print("  A          : {:.6f} m2".format(SECTION["A"]))
    print("  Ix         : {:.6f} m4".format(SECTION["Ix"]))
    print("  Iy         : {:.6f} m4".format(SECTION["Iy"]))
    print("  J          : {:.6f} m4".format(SECTION["J"]))

    print()
    print("GRILLAGE")
    print("-" * 75)
    print("  L          : {:.3f} m".format(L))
    print("  N station  : {}".format(N_STATION))
    print("  N line     : {}".format(N_LINE))
    print("  z_ref      : {}".format(Z_REF))
    print("  z_node     : {}".format(
        tuple(round(z, 6) for z in Z_NODE)
    ))

    # --------------------------------------------------------
    # EQUIVALENT BEAM
    # --------------------------------------------------------

    delta_eq = equivalent_beam_deflection()

    print()
    print("EQUIVALENT BEAM")
    print("-" * 75)
    print("  EI          : {:.6e} kNm2".format(
        E * SECTION["Ix"]
    ))
    print("  W total     : {:.3f} kN".format(W_TOTAL))
    print("  w           : {:.3f} kN/m".format(
        W_TOTAL / L
    ))
    print("  delta mid   : {:.6f} m".format(delta_eq))
    print("  delta mid   : {:.3f} mm".format(
        delta_eq * 1000.0
    ))

    # --------------------------------------------------------
    # GRILLAGE
    # --------------------------------------------------------

    node = build_grillage()

    apply_supports(node)

    total_load = apply_load(node)

    print()
    print("LOAD CHECK")
    print("-" * 75)
    print("  Target      : {:.6f} kN".format(W_TOTAL))
    print("  Applied     : {:.6f} kN".format(total_load))
    print("  Difference  : {:.6e} kN".format(
        total_load - W_TOTAL
    ))

    if abs(total_load - W_TOTAL) > 1.0e-8:
        raise RuntimeError(
            "Total load tidak konservatif."
        )

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    run_analysis()

    delta_grillage, line_disp = get_midspan_deflection(node)

    delta_grillage_abs = abs(delta_grillage)

    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    rel_error = abs(
        delta_grillage_abs - delta_eq
    ) / delta_eq

    print()
    print("MIDSPAN DEFLECTION")
    print("-" * 75)

    for j, uy in enumerate(line_disp):
        print(
            "  Line {:d} z={:8.4f} m : {:12.6f} mm".format(
                j + 1,
                Z_NODE[j],
                uy * 1000.0,
            )
        )

    print()
    print("  Grillage avg : {:.6f} m".format(
        delta_grillage_abs
    ))

    print("  Grillage avg : {:.3f} mm".format(
        delta_grillage_abs * 1000.0
    ))

    print("  Equivalent   : {:.3f} mm".format(
        delta_eq * 1000.0
    ))

    print("  Rel. error   : {:.2f} %".format(
        rel_error * 100.0
    ))

    # --------------------------------------------------------
    # SANITY CRITERION
    # --------------------------------------------------------

    print()
    print("SANITY CHECK")
    print("-" * 75)

    if rel_error <= REL_TOL_PASS:

        print(
            "  PASS : error <= {:.1f}%".format(
                REL_TOL_PASS * 100.0
            )
        )

    elif rel_error <= REL_TOL_WARN:

        print(
            "  WARNING : {:.1f}% < error <= {:.1f}%".format(
                REL_TOL_PASS * 100.0,
                REL_TOL_WARN * 100.0,
            )
        )

    else:

        print(
            "  FAIL : error > {:.1f}%".format(
                REL_TOL_WARN * 100.0
            )
        )

        raise AssertionError(
            "Equivalent beam sanity check gagal: "
            "relative error = {:.2f}%".format(
                rel_error * 100.0
            )
        )

    print()
    print("=" * 75)
    print("TEST SELESAI")
    print("=" * 75)

    ops.wipe()


if __name__ == "__main__":
    main()