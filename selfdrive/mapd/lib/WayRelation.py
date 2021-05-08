#pylint: skip-file
# flake8: noqa
from selfdrive.mapd.lib.geo import DIRECTION, R, vectors
from selfdrive.config import Conversions as CV
from datetime import datetime
import numpy as np
import re


_WAY_BBOX_PANNING = 1.6e-06  # 10 mts of paning to bounding box. (expressed in radians)

# you can find yours https://wiki.openstreetmap.org/wiki/Default_speed_limits#cite_note-177
_COUNTRY_LIMITS_KPH = {
    'US-AZ': {
        'motorway': 105.,
        'school_zone': 24.,
        'trunk': 88.,
        'primary': 88.,
        'secondary': 72.,
        'tertiary': 56.,
        'unclassified': 72.,
        'residential': 40.,
        'service': 40.
      
     'US-NY': {
        'motorway': 105.,
        'school_zone': 40.,
        'trunk': 88.,
        'primary': 88.,
        'secondary': 72.,
        'tertiary': 65.,
        'unclassified': 80.,
        'residential': 32.,
        'service': 40.
    }
}

_WD = {
    'Mo': 0,
    'Tu': 1,
    'We': 2,
    'Th': 3,
    'Fr': 4,
    'Sa': 5,
    'Su': 6
}

_ALL_WD = _WD.values()


def is_osm_time_condition_active(condition_string):
  """
  Will indicate if a time condition for a restriction as described
  @ https://wiki.openstreetmap.org/wiki/Conditional_restrictions
  is active for the current date and time of day.
  """
  now = datetime.now().astimezone()
  today = now.date()
  week_days = []

  # Look for days of week matched and validate if today matches criteria.
  dr = re.findall(r'(Mo|Tu|We|Th|Fr|Sa|Su[-,\s]*?)', condition_string)

  if len(dr) == 1:
    week_days = [_WD[dr[0]]]
  # If two or more matches condider it a range of days between 1st and 2nd element.
  elif len(dr) > 1:
    week_days = list(range(_WD[dr[0]], _WD[dr[1]] + 1))

  # If valid week days list is not empy and today day is not in the list, then the time-date range is not active.
  if len(week_days) > 0 and now.weekday() not in week_days:
    return False

  # Look for time ranges on the day. No time range, means all day
  tr = re.findall(r'([0-9]{1,2}:[0-9]{2})\s*?-\s*?([0-9]{1,2}:[0-9]{2})', condition_string)

  # if no time range but there were week days set, consider it active during the whole day
  if len(tr) == 0:
    return len(dr) > 0

  # Search among time ranges matched, one where now time belongs too. If found range is active.
  for times_tup in tr:
    times = list(map(lambda tt: datetime.
                 combine(today, datetime.strptime(tt, '%H:%M').time().replace(tzinfo=now.tzinfo)), times_tup))
    if now >= times[0] and now <= times[1]:
      return True

  return False


def speed_limit_for_osm_tag_limit_string(limit_string):
  # https://wiki.openstreetmap.org/wiki/Key:maxspeed
  if limit_string is None:
    # When limit is set to 0. is considered not existing.
    return 0.

  # Look for matches of speed by default in kph, or in mph when explicitly noted.
  v = re.match(r'^\s*([0-9]{1,3})\s*?(mph)?\s*$', limit_string)
  if v is not None:
    conv = CV.MPH_TO_MS if v[2] is not None and v[2] == "mph" else CV.KPH_TO_MS
    limit = conv * float(v[1])

  else:
    # Look for matches of speed with country implicit values.
    v = re.match(r'^\s*([A-Z]{2}):([a-z_]+):?([0-9]{1,3})?(\s+)?(mph)?\s*', limit_string)

    if v is not None:
      if v[2] == "zone" and v[3] is not None:
        conv = CV.MPH_TO_MS if v[5] is not None and v[5] == "mph" else CV.KPH_TO_MS
        limit = conv * float(v[3])
      elif v[1] in _COUNTRY_LIMITS_KPH and v[2] in _COUNTRY_LIMITS_KPH[v[1]]:
        limit = _COUNTRY_LIMITS_KPH[v[1]][v[2]] * CV.KPH_TO_MS

  return limit


def conditional_speed_limit_for_osm_tag_limit_string(limit_string):
  if limit_string is None:
    # When limit is set to 0. is considered not existing.
    return 0.

  # Look for matches of the `<restriction-value> @ (<condition>)` format
  v = re.match(r'^(.*)@\s*\((.*)\).*$', limit_string)
  if v is None:
    return 0.  # No valid format match

  value = speed_limit_for_osm_tag_limit_string(v[1])
  if value == 0.:
    return 0.  # Invalid speed limit value

  # Look for date-time conditions separated by semicolon
  v = re.findall(r'(?:;|^)([^;]*)', v[2])
  for datetime_condition in v:
    if is_osm_time_condition_active(datetime_condition):
      return value

  # If we get here, no current date-time conditon is active.
  return 0.


def bearing_to_points(point, points):
  """Calculate the bearings (angle from true north clockwise) of the vectors between `point` and each
  one of the entries in `points`. Both `point` and `points` elements are 2 element arrays containing a latitud,
  longitude pair in radians.
  """
  delta = points - point
  x = np.sin(delta[:, 1]) * np.cos(points[:, 0])
  y = np.cos(point[0]) * np.sin(points[:, 0]) - (np.sin(point[0]) * np.cos(points[:, 0]) * np.cos(delta[:, 1]))
  return np.arctan2(x, y)


def distance_to_points(point, points):
  """Calculate the distance of the vectors between `point` and each one of the entries in `points`.
  Both `point` and `points` elements are 2 element arrays containing a latitud, longitude pair in radians.
  """
  delta = points - point
  a = np.sin(delta[:, 0] / 2)**2 + np.cos(point[0]) * np.cos(points[:, 0]) * np.sin(delta[:, 1] / 2)**2
  c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
  return c * R


class WayRelation():
  """A class that represent the relationship of an OSM way and a given `location` and `bearing` of a driving vehicle.
  """
  def __init__(self, way, location=None, bearing=None):
    self.way = way
    self.reset_location_variables()
    self.direction = DIRECTION.NONE
    self.distance_to_node_ahead = 0.
    self._speed_limit = None

    # Create a numpy array with nodes data to support calculations.
    self._nodes_np = np.radians(np.array([[nd.lat, nd.lon] for nd in way.nodes], dtype=float))

    # Define bounding box to ease the process of locating a node in a way.
    # [[min_lat, min_lon], [max_lat, max_lon]]
    self.bbox = np.row_stack((np.amin(self._nodes_np, 0) - _WAY_BBOX_PANNING,
                              np.amax(self._nodes_np, 0) + _WAY_BBOX_PANNING))

    if location is not None and bearing is not None:
      self.update(location, bearing)

  def __repr__(self):
    return f'(id: {self.id}, name: {self.name}, ref: {self.ref}, ahead: {self.ahead_idx}, \
           behind: {self.behind_idx}, {self.direction}, active: {self.active})'

  def reset_location_variables(self):
    self.location = None
    self.bearing = None
    self.active = False
    self.ahead_idx = None
    self.behind_idx = None
    self._active_bearing_delta = None
    self._distance_to_way = None

  @property
  def id(self):
    return self.way.id

  def update(self, location, bearing):
    """Will update and validate the associated way with a given `location` and `bearing`.
       Specifically it will find the nodes behind and ahead of the current location and bearing.
       If no proper fit to the way geometry, the way relation is marked as invalid.
    """
    self.reset_location_variables()

    # Ignore if location not in way bounding box
    if not self.is_location_in_bbox(location):
      return

    location_rad = np.radians(np.array(location))
    bearing_rad = np.radians(bearing)

    # - Get the distance and bearings from location to all nodes. (N)
    bearings = bearing_to_points(location_rad, self._nodes_np)
    distances = distance_to_points(location_rad, self._nodes_np)

    # - Get absolute bearing delta to current driving bearing. (N)
    delta = np.abs(bearing_rad - bearings)

    # - Nodes are ahead if the cosine of the delta is positive (N)
    is_ahead = np.cos(delta) >= 0.

    # - Possible locations on the way are those where adjacent nodes change from ahead to behind or viceversa.
    possible_idxs = np.nonzero(np.diff(is_ahead))[0]

    # - when no possible locations found, then the location is not in this way.
    if len(possible_idxs) == 0:
      return

    # - Get the vectors representation of the segments betwheen consecutive nodes. (N-1, 2)
    v = vectors(self._nodes_np) * R

    # - Calculate the vector magnitudes (or distance) between nodes. (N-1)
    d = np.linalg.norm(v, axis=1)

    # - Find then angle formed between the vectors from the current location to consecutive nodes. This is the
    # absolute value of the difference in the bearings of the vectors.
    teta = np.abs(np.diff(bearings))

    # - When two consecutive nodes will be ahead and behind, they will form a triangle with the current location.
    # We find the closest distance to the way by solving the ara of the triangle and finding the height (h)
    # https://www.mathsisfun.com/algebra/trig-area-triangle-without-right-angle.html
    h = distances[:-1] * distances[1:] * np.sin(teta) / d

    # - Calculate the bearing (from true north clockwise) for every section of the way (vectors between nodes). (N-1)
    bw = np.arctan2(v[:, 0], v[:, 1])

    # - Calculate the delta between driving bearing and way bearings. (N-1)
    bw_delta = bw - bearing_rad

    # - The absolut value of the sin of `bw_delta` indicates how close the bearings match independent of direction.
    # We will use this value along the distance to the way to aid on way selection. (N-1)
    abs_sin_bw_delta = np.abs(np.sin(bw_delta))

    # - Get the delta to way bearing indicators and the distance to the way for the possible locations.
    abs_sin_bw_delta_possible = abs_sin_bw_delta[possible_idxs]
    h_possible = h[possible_idxs]

    # - Get the index where the distance to the way is minimum. That is the chosen location.
    min_h_possible_idx = np.argmin(h_possible)
    min_delta_idx = possible_idxs[min_h_possible_idx]

    # Populate location variables with result
    if is_ahead[min_delta_idx]:
      self.direction = DIRECTION.BACKWARD
      self.ahead_idx = min_delta_idx
      self.behind_idx = min_delta_idx + 1
    else:
      self.direction = DIRECTION.FORWARD
      self.ahead_idx = min_delta_idx + 1
      self.behind_idx = min_delta_idx

    self._distance_to_way = h[min_delta_idx]
    self._active_bearing_delta = abs_sin_bw_delta_possible[min_h_possible_idx]
    self.distance_to_node_ahead = distances[self.ahead_idx]
    self.active = True
    self.location = location
    self.bearing = bearing
    self._speed_limit = None

  def update_direction_from_starting_node(self, start_node_id):
    self._speed_limit = None
    if self.way.nodes[0].id == start_node_id:
      self.direction = DIRECTION.FORWARD
    elif self.way.nodes[-1].id == start_node_id:
      self.direction = DIRECTION.BACKWARD
    else:
      self.direction = DIRECTION.NONE

  def is_location_in_bbox(self, location):
    """Indicates if a given location is contained in the bounding box surrounding the way.
       self.bbox = [[min_lat, min_lon], [max_lat, max_lon]]
    """
    radians = np.radians(np.array(location, dtype=float))
    is_g = np.greater_equal(radians, self.bbox[0, :])
    is_l = np.less_equal(radians, self.bbox[1, :])

    return np.all(np.concatenate((is_g, is_l)))

  @property
  def speed_limit(self):
    if self._speed_limit is not None:
      return self._speed_limit

    # Get string from corresponding tag, consider conditional limits first.
    limit_string = self.way.tags.get("maxspeed:conditional")
    if limit_string is None:
      if self.direction == DIRECTION.FORWARD:
        limit_string = self.way.tags.get("maxspeed:forward:conditional")
      elif self.direction == DIRECTION.BACKWARD:
        limit_string = self.way.tags.get("maxspeed:backward:conditional")

    limit = conditional_speed_limit_for_osm_tag_limit_string(limit_string)

    # When no conditional limit set, attempt to get from regular speed limit tags.
    if limit == 0.:
      limit_string = self.way.tags.get("maxspeed")
      if limit_string is None:
        if self.direction == DIRECTION.FORWARD:
          limit_string = self.way.tags.get("maxspeed:forward")
        elif self.direction == DIRECTION.BACKWARD:
          limit_string = self.way.tags.get("maxspeed:backward")

      limit = speed_limit_for_osm_tag_limit_string(limit_string)

    self._speed_limit = limit
    return self._speed_limit

  @property
  def ref(self):
    return self.way.tags.get("ref", None)

  @property
  def name(self):
    return self.way.tags.get("name", None)

  @property
  def active_bearing_delta(self):
    """Returns the sine of the delta between the current location bearing and the exact
       bearing of the portion of way we are currentluy located at.
    """
    return self._active_bearing_delta

  @property
  def distance_to_way(self):
    """Returns the perpendicular (i.e. minimum) distance between current location and the way
    """
    return self._distance_to_way

  @property
  def node_behind(self):
    return self.way.nodes[self.behind_idx] if self.behind_idx is not None else None

  @property
  def node_ahead(self):
    return self.way.nodes[self.ahead_idx] if self.ahead_idx is not None else None

  @property
  def last_node(self):
    """Returns the last node on the way considering the traveling direction
    """
    if self.direction == DIRECTION.FORWARD:
      return self.way.nodes[-1]
    if self.direction == DIRECTION.BACKWARD:
      return self.way.nodes[0]
    return None

  def edge_on_node(self, node_id):
    """Indicates if the associated way starts or ends in the node with `node_id`
    """
    return self.way.nodes[0].id == node_id or self.way.nodes[-1].id == node_id

  def node_before_edge_coordinates(self, node_id):
    """Returns the coordinates of the node before the edge node identifeid with `node_id`
    """
    if self.way.nodes[0].id == node_id:
      return np.array([self.way.nodes[1].lat, self.way.nodes[1].lon], dtype=float)

    if self.way.nodes[-1].id == node_id:
      return np.array([self.way.nodes[-2].lat, self.way.nodes[-2].lon], dtype=float)

    return np.array([0., 0.])

  def next_wr(self, way_relations):
    """Returns a tuple with the next way relation (if any) based on `location` and `bearing` and
    the `way_relations` list excluding the found next way relation. (to help with recursion)
    """
    if self.direction not in [DIRECTION.FORWARD, DIRECTION.BACKWARD]:
      return None, way_relations

    def continuation_factor(next_wr):
      """Indicates how much the `next_wr` looks like a straight continuation of the current one.
      A min value of `0` indicates the `next_wr` continues with the exact same bearing as current.
      A max value of `2` indicates the `next_wr` continues in the complete oposite direction to current.
      """
      ref_point = np.array([self.last_node.lat, self.last_node.lon], dtype=float)
      adjacent_points = np.row_stack((self.node_before_edge_coordinates(self.last_node.id),
                                      next_wr.node_before_edge_coordinates(self.last_node.id)))
      bearings = bearing_to_points(np.radians(ref_point), np.radians(adjacent_points))
      delta = np.diff(bearings)[0]
      return np.cos(delta) + 1

    possible_next_wr = list(filter(lambda wr: wr.id != self.id and wr.edge_on_node(self.last_node.id), way_relations))
    possible_next_wr.sort(key=lambda wr: continuation_factor(wr))
    possibles = len(possible_next_wr)

    if possibles == 0:
      return None, way_relations

    if possibles == 1 or (self.ref is None and self.name is None):
      next_wr = possible_next_wr[0]
    else:
      next_wr = next((wr for wr in possible_next_wr if wr.has_name_or_ref(self.name, self.ref)), possible_next_wr[0])

    next_wr.update_direction_from_starting_node(self.last_node.id)
    updated_way_relations = list(filter(lambda wr: wr.id != next_wr.id, way_relations))

    return next_wr, updated_way_relations

  def has_name_or_ref(self, name, ref):
    if ref is not None and self.ref is not None and self.ref == ref:
      return True
    if name is not None and self.name is not None and self.name == name:
      return True
    return False
