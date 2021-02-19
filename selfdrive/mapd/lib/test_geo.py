import unittest
from decimal import Decimal
from math import pi, sqrt
from .geo import coord_to_rad, distance, bearing, xy, distance_and_bearing, bearing_delta, DIRECTION, \
    absoule_delta_with_direction, three_point_tangent_angle, three_point_curvature, xy_distance


class TestMapsdGeoLibrary(unittest.TestCase):
  # 0. coord to rad point tuple conversion
  def test_coord_to_rad(self):
    points = [
        (0., 360.),
        (Decimal(0.), Decimal(360.)),
        (Decimal(180.), Decimal(540.)),
    ]
    expected = [
        (0., 2 * pi),
        (0., 2 * pi),
        (pi, 3 * pi),
    ]
    rad_tuples = list(map(lambda p: coord_to_rad(p), points))
    self.assertEqual(rad_tuples, expected)

  # 1. test distance calculation between two points in coordiantes.
  def test_distance(self):
    a = (Decimal(0.), Decimal(0.))
    b = (Decimal(0.1), Decimal(0.1))
    c = (Decimal(0.01), Decimal(0.01))
    d = (Decimal(-0.01), Decimal(-0.01))

    dist1 = distance(a, b)
    dist2 = distance(a, c)
    dist3 = distance(b, c)
    dist4 = distance(a, d)

    self.assertAlmostEqual(dist1, 15730, 0)
    self.assertAlmostEqual(dist2, 1573, 0)
    self.assertAlmostEqual(dist3, 14157, 0)
    self.assertAlmostEqual(dist4, 1573, 0)

  # 2. Test bearing between two points
  def test_bearing(self):
    ref_point = (0., 0.)
    points = [
        (0., 1.),
        (0., -1.),
        (-1., 0.),
        (1., 0.),
    ]
    expected = [
        90.,
        270.,
        180.,
        0.,
    ]
    bearings = list(map(lambda p: bearing(ref_point, p), points))
    self.assertEqual(bearings, expected)

  # 3. Test cartesian coordinates from lat lon coordinates
  def test_xy(self):
    ref_point = (1., 1.)
    points = [
        (1., 1.01),
        (1., 0.99),
        (0.99, 1.),
        (1.01, 1.),
    ]
    expected = [
        (1112., 0),
        (-1112, 0),
        (0, -1112),
        (0, 1112),
    ]
    xys = list(map(lambda p: xy(ref_point, p), points))
    self._assertAlmostEqualListOfTuples(xys, expected)

  # 4. Test distance and bearing combined method
  def test_distance_and_bearing(self):
    a = (Decimal(0.), Decimal(0.))
    b = (Decimal(0.01), Decimal(0.01))
    dist, bearing = distance_and_bearing(a, b)

    self.assertAlmostEqual(dist, 1573, 0)
    self.assertAlmostEqual(bearing, 45, 0)

  # 5. Test bearing delta
  def test_bearing_delta(self):
    a = 0
    b = 90
    c = 180
    d = 270

    deltas = [
        bearing_delta(a, b),
        bearing_delta(a, c),
        bearing_delta(a, d),
        bearing_delta(b, a),
        bearing_delta(b, c),
        bearing_delta(d, b),
    ]
    expected = [
        -90,
        -180,
        90,
        90,
        -90,
        -180
    ]

    self.assertEqual(deltas, expected)

  # 6. Test absolute bearing delta with direction info
  def test_absoule_delta_with_direction(self):
    deltas = [
        0,
        45,
        -45,
        89,
        -89,
        90,
        -90,
        91,
        -91,
        135,
        -135,
        180,
        360
    ]
    expected = [
        (0, DIRECTION.AHEAD),
        (45, DIRECTION.AHEAD),
        (45, DIRECTION.AHEAD),
        (89, DIRECTION.AHEAD),
        (89, DIRECTION.AHEAD),
        (90, DIRECTION.NONE),
        (90, DIRECTION.NONE),
        (89, DIRECTION.BEHIND),
        (89, DIRECTION.BEHIND),
        (45, DIRECTION.BEHIND),
        (45, DIRECTION.BEHIND),
        (0, DIRECTION.BEHIND),
        (0, DIRECTION.AHEAD),
    ]

    d_and_d = list(map(lambda d: absoule_delta_with_direction(d), deltas))
    self.assertEqual(d_and_d, expected)

  # 7. Test tangent angle estimation from three points
  def test_three_point_tangent_angle(self):
    a = (0.99, 0.99)
    b = (0.99, 1.01)
    c = (1.01, 1.01)
    d = (1.01, 0.99)

    angles = [
        three_point_tangent_angle(a, b, c),
        three_point_tangent_angle(b, c, d),
        three_point_tangent_angle(c, d, a),
        three_point_tangent_angle(d, a, b),
    ]
    expected = [
        pi / 4.,
        -pi / 4.,
        -3 * pi / 4.,
        3 * pi / 4.,
    ]

    self.assertEqual(angles, expected, 4)

  # 8. Test the curvature estimation from three points
  def test_three_point_curvature(self):
    data = [
        ((0., 10.), (2.5, 12.5), (5., 15.), 3 * pi / 8., pi / 4., pi / 8.),
        ((0., 10.), (-2.5, 12.5), (-5., 15.), 5 * pi / 8., 3 * pi / 4., 7 * pi / 8.),
        ((0., -10.), (-2.5, -12.5), (-5., -15.), 11 * pi / 8., 5 * pi / 4., 9 * pi / 8.),
        ((0., -10.), (2.5, -12.5), (5., -15.), -3 * pi / 8., -pi / 4., -pi / 8.),
    ]

    curvatures = list(map(lambda d: three_point_curvature(d[0], d[1], d[2], d[3], d[4], d[5]), data))
    expected = [
        -0.11107,
        0.11107,
        -0.11107,
        0.11107,
    ]

    self._assertAlmostEqualList(curvatures, expected, 3)

  # 9. Test cartesian distance
  def test_xy_distance(self):
    v = sqrt(50)
    a = (v, v)
    b = (-v, -v)
    c = (-v, v)

    distances = [
        xy_distance(a, b),
        xy_distance(a, c),
        xy_distance(b, c),
        xy_distance(c, b),
        xy_distance(c, a),
        xy_distance(b, a),
    ]
    expected = [
        20,
        2 * v,
        2 * v,
        2 * v,
        2 * v,
        20
    ]

    self.assertEqual(distances, expected)

  # Helpers
  def _assertAlmostEqualList(self, a, b, places=0):
      for idx, el_a in enumerate(a):
        self.assertAlmostEqual(el_a, b[idx], places)

  def _assertAlmostEqualListOfTuples(self, a, b, places=0):
    for idx, el_a in enumerate(a):
      for idy, el_el_a in enumerate(el_a):
        self.assertAlmostEqual(el_el_a, b[idx][idy], places)
