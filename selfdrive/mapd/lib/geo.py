from math import sin, cos, sqrt, atan2, radians, degrees
from enum import Enum


R = 6373000.0  # approximate radius of earth in mt
CURVATURE_OFFSET = 300  # mts. The distance offset for curvature calculation
MAX_DIST_FOR_CURVATURE = 500  # mts. Max distance between nodes for curvature calculation


def coord_to_rad(point):
  """Tranform coordinates in degrees to radians
  """
  return tuple(map(lambda p: radians(p), point))


def distance(point_a, point_b):
  """Calculate the distance in meters between two points expressed in coordinates in degrees (lat, lon)
  """
  point_a_in_rad = coord_to_rad(point_a)
  point_b_in_rad = coord_to_rad(point_b)
  return _distance_from_rad(point_a_in_rad, point_b_in_rad)


def _distance_from_rad(point_a_in_rad, point_b_in_rad):
  """Calculate the distance in meters between two points expressed in coordinates in radians (lat, lon)
  """
  (latA, lonA) = point_a_in_rad
  (latB, lonB) = point_b_in_rad

  dlon = lonB - lonA
  dlat = latB - latA

  a = sin(dlat / 2)**2 + cos(latA) * cos(latB) * sin(dlon / 2)**2
  c = 2 * atan2(sqrt(a), sqrt(1 - a))

  return R * c


def bearing(point_a, point_b):
  """Calculate the angle in degrees between to true north and a line joining two points expresed
  in coordinates in degrees (lat, lon)
  """
  point_a_in_rad = coord_to_rad(point_a)
  point_b_in_rad = coord_to_rad(point_b)
  return _bearing_from_rad(point_a_in_rad, point_b_in_rad)


def xy(ref_point, point):
  """Calculates the approximated x y cartesian coordinates for a given coordiante `point` (lat, lon in degrees)
  in reference to a reference point `ref_point`
  """
  point_a_in_rad = coord_to_rad(ref_point)
  point_b_in_rad = coord_to_rad(point)
  return _xy_from_rad(point_a_in_rad, point_b_in_rad)


def _x_y_bearing_from_rad(point_a_in_rad, point_b_in_rad):
  """Calculates the approximated x y cartesian coordinates (in mts) and the bearing angle (in degrees)
  for a given coordiante `point_b_in_rad` (lat, lon in radians) in reference to a
  reference point `point_a_in_rad` (lat, lon in radians)
  """
  (latA, lonA) = point_a_in_rad
  (latB, lonB) = point_b_in_rad

  dlon = lonB - lonA

  x = sin(dlon) * cos(latB)
  y = cos(latA) * sin(latB) - (sin(latA) * cos(latB) * cos(dlon))
  bearing = degrees(atan2(x, y))
  return x * R, y * R, (bearing + 360) % 360


def _bearing_from_rad(point_a_in_rad, point_b_in_rad):
  """Calculate the angle in degrees between to true north and a line joining two points expresed
  in coordinates in radians (lat, lon)
  """
  _, _, bearing = _x_y_bearing_from_rad(point_a_in_rad, point_b_in_rad)
  return (bearing + 360) % 360


def _xy_from_rad(point_a_in_rad, point_b_in_rad):
  """Calculates the approximated x y cartesian coordinates for a given coordiante `point_b_in_rad` (lat, lon in radians)
  in reference to a reference point `point_a_in_rad` (lat, lon in radians)
  """
  x, y, _ = _x_y_bearing_from_rad(point_a_in_rad, point_b_in_rad)
  return x, y


def distance_and_bearing(point_a, point_b):
  """ Provides distance and bearing calucations between two points in a single method call. see `distance` and 
  `bearing` for details.
  """
  point_a_in_rad = coord_to_rad(point_a)
  point_b_in_rad = coord_to_rad(point_b)

  return _distance_from_rad(point_a_in_rad, point_b_in_rad), _bearing_from_rad(point_a_in_rad, point_b_in_rad)


def bearing_delta(bearing_a, bearing_b):
  """Returns the angle difference in degrees between two bearing angles (in degrees)
  """
  return (bearing_a - bearing_b + 180) % 360 - 180


def absoule_delta_with_direction(delta):
  """Takes a `bearing_delta` and provides its absolute value ignoring its direction. The direction is then
  provided as an additional element on the result tuple.
  If delta is between -90 and 90, direction is AHEAD, between 90 and 270 is BEHIND.
  """
  delta_ahead = abs(bearing_delta(delta, 0.))
  delta_behind = abs(delta_ahead - 180)

  if delta_ahead < delta_behind:
    return (delta_ahead, DIRECTION.AHEAD)
  elif delta_ahead > delta_behind:
    return (delta_behind, DIRECTION.BEHIND)
  else:
    return (delta_ahead, DIRECTION.NONE)


def three_point_curvature_alt(ref, prev, next):
  # https://math.stackexchange.com/questions/2507540/numerical-way-to-solve-for-the-curvature-of-a-curve
  # https://en.wikipedia.org/wiki/Heron%27s_formula
  prev_r = (prev[0] - ref[0], prev[1] - ref[1])
  next_r = (next[0] - ref[0], next[1] - ref[1])

  prev_ang = atan2(prev_r[0], prev_r[1])
  next_ang = atan2(next_r[0], next_r[1])
  a = CURVATURE_OFFSET
  b = CURVATURE_OFFSET

  prev_n = (a * cos(prev_ang), a * sin(prev_ang))
  next_n = (b * cos(next_ang), b * sin(next_ang))

  c = xy_distance(next_n, prev_n)
  s = (a + b + c) / 2.
  A = sqrt(s * (s - a) * (s - b) * (s - c))

  return 4 * A / (a * b * c)


def three_point_tangent_angle(prev, ref, next):
  """Angle (in readians) of the tangent line formed by three points in sequence `prev`, `ref`, `next`
  """
  # https://www.math24.net/curvature-radius
  prev_vec = (ref[0] - prev[0], ref[1] - prev[1])
  next_vec = (next[0] - ref[0], next[1] - ref[1])
  avg_vec = ((prev_vec[0] + next_vec[0]) / 2., (prev_vec[1] + next_vec[1]) / 2.)

  return atan2(avg_vec[1], avg_vec[0])


def three_point_curvature(prev_xy, ref_xy, next_xy, prev_tan, ref_tan, next_tan):
  """Aproximated curvature for a line joining 3 points with calculated tangent angles. Aproximation by
  averaging the variation of the tangent angle over distance.
  """
  prev_tan_delta = ref_tan - prev_tan if prev_tan is not None else 0
  prev_dist = min(xy_distance(prev_xy, ref_xy), MAX_DIST_FOR_CURVATURE)
  next_tan_delta = next_tan - ref_tan if next_tan is not None else 0
  next_dist = min(xy_distance(next_xy, ref_xy), MAX_DIST_FOR_CURVATURE)

  prev_curv = prev_tan_delta / prev_dist
  next_curv = next_tan_delta / next_dist

  return (prev_curv + next_curv) / 2.


def xy_distance(A, B):
  """Distance between two point on a cartesian plane.
  """
  return sqrt((A[0] - B[0])**2 + (A[1] - B[1])**2)


class DIRECTION(Enum):
  NONE = 0
  AHEAD = 1
  BEHIND = 2
  FORWARD = 3
  BACKWARD = 4
