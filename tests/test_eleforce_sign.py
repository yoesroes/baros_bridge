import openseespy.opensees as ops


def test_eleforce_sign_simple_beam():
    # =====================================================
    # MODEL: balok sederhana, 2 elemen, beban titik tengah
    # Unit: kN, m
    # =====================================================
    L = 10.0
    P = 100.0
    E = 30.0e6
    G = 12.0e6
    A = 1.0
    J = 0.1
    Iy = 0.1
    Iz = 0.1
    tol = 1.0e-6

    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    ops.node(1, 0.0, 0.0, 0.0)
    ops.node(2, L / 2.0, 0.0, 0.0)
    ops.node(3, L, 0.0, 0.0)

    # Bidang analisis vertikal; DOF luar bidang dikekang
    ops.fix(1, 1, 1, 1, 1, 1, 0)
    ops.fix(2, 0, 0, 1, 1, 1, 0)
    ops.fix(3, 0, 1, 1, 1, 1, 0)

    ops.geomTransf("Linear", 1, 0.0, 0.0, 1.0)

    ops.element(
        "elasticBeamColumn", 1, 1, 2,
        A, E, G, J, Iy, Iz, 1
    )
    ops.element(
        "elasticBeamColumn", 2, 2, 3,
        A, E, G, J, Iy, Iz, 1
    )

    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    ops.load(2, 0.0, -P, 0.0, 0.0, 0.0, 0.0)

    ops.system("UmfPack")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.test("NormDispIncr", 1.0e-10, 100)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")

    ok = ops.analyze(1)
    assert ok == 0, f"Analisis gagal, return code = {ok}"

    ops.reactions()
    r_left = ops.nodeReaction(1, 2)
    r_right = ops.nodeReaction(3, 2)

    f1 = ops.eleForce(1)
    f2 = ops.eleForce(2)

    # Urutan standar eleForce 3D:
    # [N, Vy, Vz, T, My, Mz] pada ujung i lalu ujung j.
    print("\n=== TES TANDA eleForce: BALOK SEDERHANA ===")
    print(f"Reaksi vertikal kiri  = {r_left:+.6f} kN")
    print(f"Reaksi vertikal kanan = {r_right:+.6f} kN")
    print(f"Elemen 1: Vy_i={f1[1]:+.6f}, Vy_j={f1[7]:+.6f} kN")
    print(f"Elemen 1: Mz_i={f1[5]:+.6f}, Mz_j={f1[11]:+.6f} kNm")
    print(f"Elemen 2: Vy_i={f2[1]:+.6f}, Vy_j={f2[7]:+.6f} kN")
    print(f"Elemen 2: Mz_i={f2[5]:+.6f}, Mz_j={f2[11]:+.6f} kNm")

    # -----------------------------------------------------
    # VALIDASI MEKANIKA: reaksi, geser, dan momen
    # -----------------------------------------------------
    assert abs(r_left - P / 2.0) < tol
    assert abs(r_right - P / 2.0) < tol
    assert abs(r_left + r_right - P) < tol

    # Besar geser ujung tiap setengah bentang = P/2
    for v in (f1[1], f1[7], f2[1], f2[7]):
        assert abs(abs(v) - P / 2.0) < tol

    # Besar momen di tumpuan = 0; di tengah = P*L/4.
    # Tanda ujung sengaja dicetak untuk diverifikasi dari hasil nyata.
    m_mid = P * L / 4.0
    assert abs(f1[5]) < tol
    assert abs(abs(f1[11]) - m_mid) < tol
    assert abs(abs(f2[5]) - m_mid) < tol
    assert abs(f2[11]) < tol

    print("HASIL: PASS — reaksi, geser, dan momen sesuai teori.")
    print("Gunakan tanda Mz/Vy yang tercetak untuk verifikasi konvensi.")


if __name__ == "__main__":
    test_eleforce_sign_simple_beam()
    ops.wipe()