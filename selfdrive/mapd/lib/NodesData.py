import numpy as np
from enum import Enum
from selfdrive.mapd.lib.geo import DIRECTION, R


def vectors(points):
  """Provides a array of vectors on cartesian space (x, y).
     Each vector represents the path from a point in `points` to the next.
     `points` must by a (N, 2) array of [lat, lon] pairs in radians.
  """
  latA = points[:-1, 0]
  latB = points[1:, 0]
  delta = np.diff(points, axis=0)
  dlon = delta[:, 1]

  x = np.sin(dlon) * np.cos(latB)
  y = np.cos(latA) * np.sin(latB) - (np.sin(latA) * np.cos(latB) * np.cos(dlon))

  return np.column_stack((x, y))


def nodes_raw_data_array_for_wr(wr, drop_last=False):
  """Provides an array of raw node data (id, lat, lon, speed_limit) for all nodes in way relation
  """
  sl = wr.speed_limit if wr.speed_limit is not None else 0.
  data = np.array(list(map(lambda n: (n.id, n.lat, n.lon, sl), wr.way.nodes)), dtype=float)

  # reverse the order if way direction is backwards
  if wr.direction == DIRECTION.BACKWARD:
    data = np.flip(data, axis=0)

  # drop last if requested
  return data[:-1] if drop_last else data


def node_calculations(points):
  """Provides node calculations based on an array of (lat, lon) points in radians.
     points is a (N x 1) array where N >= 3
  """
  if len(points) < 3:
    raise(IndexError)

  # Get the vector representation of node points in cartesian plane.
  # (N-1, 2) array. Not including (0., 0.)
  v = vectors(points) * R

  # Calculate the vector magnitudes (or distance)
  # (N-1, 1) array. No distance for v[-1]
  d = np.linalg.norm(v, axis=1)

  # Calculate angles between vectors when stack one after the other.
  # https://math.stackexchange.com/questions/2610186/discrete-points-curvature-analysis
  # (N-2, 1) array. v[0] and v[-1] have no angle
  dot = np.sum(-v[:-1] * v[1:], axis=1)
  a = np.arccos(dot / (d[:-1] * d[1:]))

  # Calculate the curvature from the circumcircle of a triangle
  # https://www.mathopenref.com/trianglecircumcircle.html
  # (N-2, 1) array. v[0] and v[-1] have no curvature
  c = 2. * np.sin(a) / np.linalg.norm(v[:-1] + v[1:], axis=1)

  # Calculate the bearing (from true north clockwise) for every node.
  # (N-1, 1) array. No bearing for v[-1]
  b = np.arctan2(v[:, 0], v[:, 1])

  # Pad the outputs to match the size of arrays to N

  # Add origin to vector space. (i.e first node in list)
  v = np.concatenate(([[0., 0.]], v))
  # Provide distance to previous node and distance to next node
  dp = np.concatenate(([0.], d))
  dn = np.concatenate((d, [0.]))
  # Angles on edge nodes should be pi. i.e. a straight line.
  a = np.concatenate(([[np.pi], a, [np.pi]]))
  # Curvature on edges should be 0. i.e a straight line.
  c = np.concatenate(([[0.], c, [0.]]))
  # Bearing of last node should keep bearing from previous.
  b = np.concatenate((b, [b[-1]]))

  return v, dp, dn, a, c, b


class SpeedLimitSection():
  """And object representing a speed limited road section ahead.
  provides the start and end distance and the speed limit value
  """
  def __init__(self, start, end, value):
    self.start = start
    self.end = end
    self.value = value

  def __repr__(self):
    return f'from: {self.start}, to: {self.end}, limit: {self.value}'


class NodeDataIdx(Enum):
  """Column index for data elements on NodesData underlying data store.
  """
  node_id = 0
  lat = 1
  lon = 2
  speed_limit = 3
  x = 4             # x value of cartesian vector representing the section between last node and this node.
  y = 5             # y value of cartesian vector representing the section between last node and this node.
  dist_prev = 6     # distance to previous node.
  dist_next = 7     # distance to next node
  angle = 8         # angles between line segments coming into this node and leaving this node.
  curvature = 9     # estimated curvature at this node.
  bearing = 10      # bearing of the vector departin from this node.


class NodesData:
  """Container for the list of node data from a ordered list of way relations to be used in a Route
  """
  def __init__(self, way_relations):
    self._nodes_data = np.array([])

    way_count = len(way_relations)
    if way_count == 0:
      return

    # We want all the nodes from the last way section
    nodes_data = nodes_raw_data_array_for_wr(way_relations[-1])

    # For the ways before the last in the route we want all the nodes but the last, as that one is the first on
    # the next section. Collect them, append last way node data and concatenate the numpy arrays.
    if way_count > 1:
      wrs_data = tuple(map(lambda wr: nodes_raw_data_array_for_wr(wr, True), way_relations[:-1]))
      wrs_data += (nodes_data,)
      nodes_data = np.concatenate(wrs_data)

    # Get a subarray with lat, lon to compute the remaining node values.
    lat_lon_array = nodes_data[:, [1, 2]]
    points = np.radians(lat_lon_array)
    # Ensure we have more than 3 points, if not calculations are not possible.
    if len(points) < 3:
      return
    vect, dist_prev, dist_next, angle, curvature, bearing = node_calculations(points)

    # append calculations to nodes_data
    # nodes_data structure: [id, lat, lon, speed_limit, x, y, dist_prev, dist_next, angle, curvature, bearing]
    self._nodes_data = np.column_stack((nodes_data, vect, dist_prev, dist_next, angle, curvature, bearing))

  @property
  def count(self):
    return len(self._nodes_data)

  def get(self, node_data_idx):
    """Returns the array containing all the elements of a specific NodeDataIdx type.
    """
    if len(self._nodes_data) == 0 or node_data_idx.value >= self._nodes_data.shape[1]:
      return np.array([])

    return self._nodes_data[:, node_data_idx.value]

  def speed_limits_ahead(self, ahead_idx, distance_to_node_ahead):
    """Returns and array of SpeedLimitSection objects for the actual route ahead of current location
    """
    if len(self._nodes_data) == 0 or ahead_idx is None:
      return []

    # Find the cumulative distances where speed limit changes. Build Speed limit sections for those.
    dist = np.concatenate(([distance_to_node_ahead], self.get(NodeDataIdx.dist_next)[ahead_idx:]))
    dist = np.cumsum(dist, axis=0)
    sl = self.get(NodeDataIdx.speed_limit)[ahead_idx - 1:]
    sl_next = np.concatenate((sl[1:], [0.]))

    # Create a boolean mask where speed limit changes and filter values
    sl_change = sl != sl_next
    distances = dist[sl_change]
    speed_limits = sl[sl_change]

    # Create speed limits sections combining all continious nodes that have same speed limit value.
    start = 0.
    limits_ahead = []
    for idx, end in enumerate(distances):
      limits_ahead.append(SpeedLimitSection(start, end, speed_limits[idx]))
      start = end

    return limits_ahead

  def curvatures_ahead(self, ahead_idx, distance_to_node_ahead):
    """Provides a numpy array of ordered pairs by distance including the distance ahead and the curvature.
    """
    if len(self._nodes_data) == 0 or ahead_idx is None:
      return np.array([])

    # Find the cumulative distances to nodes and its curvature
    dist = np.concatenate(([distance_to_node_ahead], self.get(NodeDataIdx.dist_next)[ahead_idx:-1]))
    dist = np.cumsum(dist, axis=0)
    curv = self.get(NodeDataIdx.curvature)[ahead_idx:]

    return np.column_stack((dist, curv))

  def distance_to_end(self, ahead_idx, distance_to_node_ahead):
    if len(self._nodes_data) == 0 or ahead_idx is None:
      return None

    return np.sum(np.concatenate(([distance_to_node_ahead], self.get(NodeDataIdx.dist_next)[ahead_idx:])))
