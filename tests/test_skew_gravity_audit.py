"""Independent OpenSees audit for gravity loading on an inclined beam.

Model A receives integrated global nodal-consistent forces/couples. Model B
uses the production local-load projection and the production eleLoad syntax.
Run with: python -m pytest -s tests/test_skew_gravity_audit.py
"""
import math

import openseespy.opensees as ops
import pytest

from core import analysis, elements


TOL_ORIENTATION = 1.0e-12
TOL_LOAD_RECONSTRUCTION = 1.0e-12
TOL_EQUILIBRIUM = 1.0e-8
TOL_MODEL_RELATIVE = 1.0e-8
TOL_REFINEMENT_RELATIVE = 2.0e-3

E = 30.0e6
G = 12.0e6
AREA = 1.2
J = 0.25
IY = 0.30
IZ = 0.40
LOAD_MAGNITUDE = -10.0


def local_axes(node_i, node_j, vecxz=(0.0, 0.0, 1.0)):
    delta = [b - a for a, b in zip(node_i, node_j)]
    length = math.sqrt(sum(value * value for value in delta))
    axis_x = [value / length for value in delta]
    axis_y = [
        vecxz[1] * axis_x[2] - vecxz[2] * axis_x[1],
        vecxz[2] * axis_x[0] - vecxz[0] * axis_x[2],
        vecxz[0] * axis_x[1] - vecxz[1] * axis_x[0],
    ]
    norm_y = math.sqrt(sum(value * value for value in axis_y))
    axis_y = [value / norm_y for value in axis_y]
    axis_z = [
        axis_x[1] * axis_y[2] - axis_x[2] * axis_y[1],
        axis_x[2] * axis_y[0] - axis_x[0] * axis_y[2],
        axis_x[0] * axis_y[1] - axis_x[1] * axis_y[0],
    ]
    return length, (axis_x, axis_y, axis_z)


def dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _integrated_nodal_load(q_global, length, axes):
    """Integrate the beam interpolation against global uniform line load."""
    local_load = [dot(axis, q_global) for axis in axes]
    wx, wy, wz = local_load
    local_ends = [
        [wx * length / 2.0, wy * length / 2.0, wz * length / 2.0,
         0.0, -wz * length**2 / 12.0, wy * length**2 / 12.0],
        [wx * length / 2.0, wy * length / 2.0, wz * length / 2.0,
         0.0, wz * length**2 / 12.0, -wy * length**2 / 12.0],
    ]
    global_ends = []
    for end in local_ends:
        force = [sum(axes[k][i] * end[k] for k in range(3))
                 for i in range(3)]
        moment = [sum(axes[k][i] * end[k + 3] for k in range(3))
                  for i in range(3)]
        global_ends.append(force + moment)
    return global_ends, local_ends


def _build_and_solve(angle, segment_loads, use_element_load):
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    elements.define_geom_transf()

    n_segments = len(segment_loads)
    horizontal_length = 10.0
    nodes = {}
    coords = {}
    for index in range(n_segments + 1):
        fraction = index / n_segments
        tag = index + 1
        point = (
            horizontal_length * fraction,
            horizontal_length * math.tan(angle) * fraction,
            0.0,
        )
        nodes[index] = tag
        coords[tag] = point
        ops.node(tag, *point)

    for index in range(n_segments):
        ops.element(
            "elasticBeamColumn", index + 1, nodes[index], nodes[index + 1],
            AREA, E, G, J, IY, IZ, elements.TRANSF_MEMANJANG,
        )

    ops.fix(nodes[0], 1, 1, 1, 1, 1, 1)
    ops.fix(nodes[n_segments], 1, 1, 1, 1, 1, 0)
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)

    reference_loads = {tag: [0.0] * 6 for tag in nodes.values()}
    equivalent_local_loads = {}
    for index, q in enumerate(segment_loads):
        n_i, n_j = nodes[index], nodes[index + 1]
        length, axes = local_axes(coords[n_i], coords[n_j])
        q_global = (0.0, q, 0.0)
        if use_element_load:
            cosine = axes[0][0]
            sine = axes[0][1]
            wy, wx = analysis.komponen_lokal(q, cosine, sine)
            ops.eleLoad("-ele", index + 1, "-type", "-beamUniform",
                        wy, 0.0, wx)
        else:
            global_equivalent, local_equivalent = _integrated_nodal_load(
                q_global, length, axes)
            equivalent_local_loads[index + 1] = local_equivalent
            for node_tag, equivalent in zip((n_i, n_j), global_equivalent):
                reference_loads[node_tag] = [
                    a + b for a, b in zip(reference_loads[node_tag], equivalent)
                ]

    if not use_element_load:
        for tag, load in reference_loads.items():
            ops.load(tag, *load)

    ops.constraints("Transformation")
    ops.numberer("RCM")
    ops.system("BandGeneral")
    ops.test("NormDispIncr", 1.0e-11, 100)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    status = ops.analyze(1)
    assert status == 0, "OpenSees analyze returned {}".format(status)
    ops.reactions()

    response = {
        "coords": coords,
        "displacements": {tag: tuple(ops.nodeDisp(tag)) for tag in nodes.values()},
        "reactions": {tag: tuple(ops.nodeReaction(tag))
                      for tag in (nodes[0], nodes[n_segments])},
        "end_forces_local": {},
        "end_forces_global": {},
        "ele_force_global": {},
        "external_force": [0.0, 0.0, 0.0],
        "external_moment": [0.0, 0.0, 0.0],
    }
    for tag, load in reference_loads.items():
        if not use_element_load:
            _add_external_resultant(response, coords[tag], load)
    for index, q in enumerate(segment_loads):
        n_i, n_j = nodes[index], nodes[index + 1]
        length, axes = local_axes(coords[n_i], coords[n_j])
        midpoint = [(a + b) / 2.0 for a, b in zip(coords[n_i], coords[n_j])]
        resultant = (0.0, q * length, 0.0, 0.0, 0.0, 0.0)
        if use_element_load:
            _add_external_resultant(response, midpoint, resultant)
        raw_global = ops.eleForce(index + 1)
        raw_local = ops.eleResponse(index + 1, "localForce")
        response["ele_force_global"][index + 1] = tuple(raw_global)
        for end_index, node_tag in enumerate((n_i, n_j)):
            local_end = raw_local[end_index * 6:(end_index + 1) * 6]
            if not use_element_load:
                consistent_load = equivalent_local_loads[index + 1][end_index]
                local_end = [force - load for force, load
                             in zip(local_end, consistent_load)]
            response["end_forces_local"][(index + 1, node_tag)] = tuple(local_end)
            global_force = [sum(axes[k][i] * local_end[k] for k in range(3))
                            for i in range(3)]
            global_moment = [sum(axes[k][i] * local_end[k + 3]
                                 for k in range(3)) for i in range(3)]
            response["end_forces_global"][(index + 1, node_tag)] = tuple(
                global_force + global_moment
            )
    return response


def _add_external_resultant(response, point, force_and_moment):
    force = force_and_moment[:3]
    moment = force_and_moment[3:]
    position_moment = cross(point, force)
    for axis in range(3):
        response["external_force"][axis] += force[axis]
        response["external_moment"][axis] += moment[axis] + position_moment[axis]


def _equilibrium_residual(response):
    force = list(response["external_force"])
    moment = list(response["external_moment"])
    for tag, reaction in response["reactions"].items():
        point = response["coords"][tag]
        for axis in range(3):
            force[axis] += reaction[axis]
        reaction_moment = cross(point, reaction[:3])
        for axis in range(3):
            moment[axis] += reaction[axis + 3] + reaction_moment[axis]
    return max(abs(value) for value in force), max(abs(value) for value in moment)


def _relative_difference(left, right):
    scale = max(1.0, *(abs(value) for value in left),
                *(abs(value) for value in right))
    return max((abs(a - b) / scale for a, b in zip(left, right)), default=0.0)


def test_project_local_axes_for_reference_skew():
    theta = math.atan2(2.0, 10.0)
    length, axes = local_axes((0.0, 0.0, 0.0), (10.0, 2.0, 0.0))
    expected_x = (math.cos(theta), math.sin(theta), 0.0)
    expected_y = (-math.sin(theta), math.cos(theta), 0.0)
    assert abs(length - math.sqrt(104.0)) < TOL_ORIENTATION
    assert max(abs(a - b) for a, b in zip(axes[0], expected_x)) < TOL_ORIENTATION
    assert max(abs(a - b) for a, b in zip(axes[1], expected_y)) < TOL_ORIENTATION
    assert max(abs(dot(axes[i], axes[j])) for i in range(3) for j in range(3)
               if i != j) < TOL_ORIENTATION
    assert max(abs(dot(axis, axis) - 1.0) for axis in axes) < TOL_ORIENTATION
    print("AXES theta={:.12f} x={} y={} z={} length={:.12f}".format(
        theta, axes[0], axes[1], axes[2], length))


def test_local_load_reconstructs_vertical_global_load():
    theta = math.atan2(2.0, 10.0)
    cosine, sine = math.cos(theta), math.sin(theta)
    wy, wx = analysis.komponen_lokal(LOAD_MAGNITUDE, cosine, sine)
    axes = local_axes((0.0, 0.0, 0.0), (10.0, 2.0, 0.0))[1]
    reconstructed = [wx * axes[0][i] + wy * axes[1][i] for i in range(3)]
    target = [0.0, LOAD_MAGNITUDE, 0.0]
    error = max(abs(a - b) for a, b in zip(reconstructed, target))
    assert error < TOL_LOAD_RECONSTRUCTION
    print("LOAD target={} local(Wy,Wz,Wx)=({:.12f},0,{:.12f}) "
          "reconstructed={} max_abs_error={:.3e}".format(
              target, wy, wx, reconstructed, error))


@pytest.mark.parametrize("angle", [0.0, math.atan2(2.0, 10.0),
                                    -math.atan2(2.0, 10.0)])
def test_eleforce_coordinate_response_on_flat_and_skew_members(angle):
    _build_and_solve(angle, [LOAD_MAGNITUDE], True)
    global_force = ops.eleForce(1)
    force_response = ops.eleResponse(1, "force")
    local_force = ops.eleResponse(1, "localForce")
    difference = max(abs(a - b) for a, b in zip(global_force, force_response))
    _, axes = local_axes((0.0, 0.0, 0.0),
                         (10.0, 10.0 * math.tan(angle), 0.0))
    reconstructed = []
    for end in range(2):
        local_end = local_force[end * 6:(end + 1) * 6]
        global_force_end = [sum(axes[k][i] * local_end[k] for k in range(3))
                            for i in range(3)]
        global_moment_end = [sum(axes[k][i] * local_end[k + 3]
                                 for k in range(3)) for i in range(3)]
        reconstructed.extend(global_force_end + global_moment_end)
    local_transform_difference = max(
        abs(a - b) for a, b in zip(global_force, reconstructed))
    assert difference < TOL_ORIENTATION
    assert local_transform_difference < TOL_ORIENTATION
    if abs(angle) > TOL_ORIENTATION:
        assert max(abs(a - b) for a, b in zip(global_force, local_force)) > 1.0
    print("ELEFORCE angle={:+.9f} eleForce/force gap={:.3e} "
          "localForce->global gap={:.3e}; global={} local={}".format(
              angle, difference, local_transform_difference,
              tuple(global_force), tuple(local_force)))


@pytest.mark.parametrize("angle", [0.0, math.atan2(2.0, 10.0),
                                    -math.atan2(2.0, 10.0)])
def test_reference_nodal_load_matches_production_eleload(angle):
    reference = _build_and_solve(angle, [LOAD_MAGNITUDE], False)
    tested = _build_and_solve(angle, [LOAD_MAGNITUDE], True)
    force_residual, moment_residual = _equilibrium_residual(tested)
    external_force_difference = _relative_difference(
        reference["external_force"], tested["external_force"])
    external_moment_difference = _relative_difference(
        reference["external_moment"], tested["external_moment"])
    reaction_difference = max(
        _relative_difference(reference["reactions"][tag],
                             tested["reactions"][tag])
        for tag in reference["reactions"]
    )
    displacement_difference = max(
        _relative_difference(reference["displacements"][tag],
                             tested["displacements"][tag])
        for tag in reference["displacements"]
    )
    force_difference = max(
        _relative_difference(reference["end_forces_global"][key],
                             tested["end_forces_global"][key])
        for key in reference["end_forces_global"]
    )
    assert force_residual < TOL_EQUILIBRIUM
    assert moment_residual < TOL_EQUILIBRIUM
    assert external_force_difference < TOL_MODEL_RELATIVE
    assert external_moment_difference < TOL_MODEL_RELATIVE
    assert reaction_difference < TOL_MODEL_RELATIVE
    assert displacement_difference < TOL_MODEL_RELATIVE
    assert force_difference < TOL_MODEL_RELATIVE
    print("COMPARE angle={:+.9f} q={} Fext={} Mext={} "
          "dFext={:.3e} dMext={:.3e} |dFbal|={:.3e} "
          "|dMbal|={:.3e} dRrel={:.3e} "
          "dUrel={:.3e} dFend_global_rel={:.3e}".format(
              angle, LOAD_MAGNITUDE, tested["external_force"],
              tested["external_moment"], external_force_difference,
              external_moment_difference, force_residual, moment_residual,
              reaction_difference, displacement_difference, force_difference))


def test_asymmetric_piecewise_load_matches_and_refines():
    angle = math.atan2(2.0, 10.0)
    segment_loads = [-8.0, -13.0, -6.0, -11.0]
    reference = _build_and_solve(angle, segment_loads, False)
    tested = _build_and_solve(angle, segment_loads, True)
    force_residual, moment_residual = _equilibrium_residual(tested)
    external_force_difference = _relative_difference(
        reference["external_force"], tested["external_force"])
    external_moment_difference = _relative_difference(
        reference["external_moment"], tested["external_moment"])
    assert force_residual < TOL_EQUILIBRIUM
    assert moment_residual < TOL_EQUILIBRIUM
    assert external_force_difference < TOL_MODEL_RELATIVE
    assert external_moment_difference < TOL_MODEL_RELATIVE
    for collection in ("reactions", "displacements", "end_forces_local",
                       "end_forces_global"):
        for key, ref_value in reference[collection].items():
            assert _relative_difference(ref_value, tested[collection][key]) \
                < TOL_MODEL_RELATIVE, (collection, key)

    mesh_responses = {}
    for count in (2, 4, 8):
        mesh_responses[count] = _build_and_solve(
            angle, [LOAD_MAGNITUDE] * count, True)
    coarse_mid = mesh_responses[2]["displacements"][2][1]
    fine_mid = mesh_responses[8]["displacements"][5][1]
    refinement_difference = abs(coarse_mid - fine_mid) / max(
        1.0e-12, abs(coarse_mid), abs(fine_mid))
    assert refinement_difference < TOL_REFINEMENT_RELATIVE
    print("ASYMMETRIC q={} dFext={:.3e} dMext={:.3e} |dFbal|={:.3e} "
          "|dMbal|={:.3e}; mesh Uy(mid) 2/8={:.9e}/{:.9e} "
          "rel_diff={:.3e} tolerance={:.3e}".format(
              segment_loads, external_force_difference,
              external_moment_difference, force_residual, moment_residual,
              coarse_mid, fine_mid, refinement_difference,
              TOL_REFINEMENT_RELATIVE))
    print("MODEL A/B shared global resultants: Fext={} Mext={}".format(
        reference["external_force"], reference["external_moment"]))
    print("MODEL A/B support reactions (global xyz + Mxyz): {}".format(
        reference["reactions"]))
    print("MODEL A/B nodal displacements (global xyz + rotations): {}".format(
        reference["displacements"]))
    print("MODEL A/B first element end actions, local then global: {} / {}".format(
        {key: value for key, value in reference["end_forces_local"].items()
         if key[0] == 1},
        {key: value for key, value in reference["end_forces_global"].items()
         if key[0] == 1}))