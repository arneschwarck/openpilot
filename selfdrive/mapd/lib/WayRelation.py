from selfdrive.mapd.lib.geo import DIRECTION, distance_and_bearing, absoule_delta_with_direction, bearing_delta, bearing
from common.numpy_fast import interp
from selfdrive.config import Conversions as CV
import numpy as np
import re


_ACCEPTABLE_BEARING_DELTA_V = [40., 20., 10., 5.]
_ACCEPTABLE_BEARING_DELTA_BP = [30., 100., 200., 300.]

_COUNTRY_LIMITS_KPH = {
    'DE': {
        'urban': 50.,
        'rural': 100.,
        'motorway': 0.,
        'living_street': 7.,
        'bicycle_road': 30.
    }
}


class WayRelation():
  """A class that represent the relationship of an OSM way and a given `location` and `bearing` of a driving vehicle.
  """
  def __init__(self, way, location=None, bearing=None):
    self.way = way
    self.reset_location_variables()
    self.direction = DIRECTION.NONE
    self._speed_limit = None

    # Create a numpy array with nodes data to support calculations.
    self._nodes_np = np.radians(np.array([[nd.lat, nd.lon] for nd in way.nodes], dtype=float))

    # Define bounding box to ease the process of locating a node in a way.
    # [[min_lat, min_lon], [max_lat, max_lon]]
    self.bbox = np.row_stack((np.amin(self._nodes_np, 0), np.amax(self._nodes_np, 0)))

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
    self._active_way_bearing = None

  @property
  def id(self):
    return self.way.id

  def update(self, location, bearing):
    """Will update and validate the associated way with a given `location` and `bearing`.
       Specifically it will find the nodes behind and ahead of the current location and bearing.
       If no proper fit to the way geometry, the way relation is marked as invalid.
    """
    self.reset_location_variables()

    # Ignore if location not in way boundingn box
    if not self.is_location_in_bbox(location):
      return

    # TODO: Do this with numpy. Calculate distance and bearing to all nodes and then process array to find
    # best match if any.
    for idx, node in enumerate(self.way.nodes):
      distance_to_node, bearing_to_node = distance_and_bearing(location, (node.lat, node.lon))
      delta, direction = absoule_delta_with_direction(bearing_delta(bearing, bearing_to_node))
      if abs(delta) > interp(distance_to_node, _ACCEPTABLE_BEARING_DELTA_BP, _ACCEPTABLE_BEARING_DELTA_V):
        continue
      if direction == DIRECTION.AHEAD:
        self.ahead_idx = idx
        self.distance_to_node_ahead = distance_to_node
        if self.behind_idx is not None:
          break
      elif direction == DIRECTION.BEHIND:
        self.behind_idx = idx
        if self.ahead_idx is not None:
          break
    # Validate
    if self.ahead_idx is None or self.behind_idx is None or abs(self.ahead_idx - self.behind_idx) > 1:
      self.reset_location_variables()
      return
    self.active = True
    self.location = location
    self.bearing = bearing
    self._speed_limit = None
    self.direction = DIRECTION.FORWARD if self.ahead_idx - self.behind_idx > 0 else DIRECTION.BACKWARD

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

    # Get string from corresponding tag
    limit_string = self.way.tags.get("maxspeed")
    if limit_string is None:
      if self.direction == DIRECTION.FORWARD:
        limit_string = self.way.tags.get("maxspeed:forward")
      elif self.direction == DIRECTION.BACKWARD:
        limit_string = self.way.tags.get("maxspeed:backward")

    # When limit is set to 0. is considered not existing. Use 0. as default value.
    limit = 0.

    # https://wiki.openstreetmap.org/wiki/Key:maxspeed
    if limit_string is not None:
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

    self._speed_limit = limit
    return self._speed_limit

  @property
  def ref(self):
    return self.way.tags.get("ref", None)

  @property
  def name(self):
    return self.way.tags.get("name", None)

  @property
  def active_bearing(self):
    """Returns the exact bearing of the portion of way we are currentluy located at.
    """
    if self._active_way_bearing is not None:
      return self._active_way_bearing
    if not self.active:
      return None
    ahead_node = self.way.nodes[self.ahead_idx]
    behind_node = self.way.nodes[self.behind_idx]
    self._active_way_bearing = bearing((behind_node.lat, behind_node.lon), (ahead_node.lat, ahead_node.lon))
    return self._active_way_bearing

  def active_bearing_delta(self, bearing):
    """Returns the delta between the given bearing and the exact
       bearing of the portion of way we are currentluy located at.
    """
    if self.active_bearing is None:
      return None
    return bearing_delta(bearing, self.active_bearing)

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

  def next_wr(self, way_relations):
    """Returns a tuple with the next way relation (if any) based on `location` and `bearing` and
    the `way_relations` list excluding the found next way relation. (to help with recursion)
    """
    if self.direction not in [DIRECTION.FORWARD, DIRECTION.BACKWARD]:
      return None, way_relations
    possible_next_wr = list(filter(lambda wr: wr.id != self.id and wr.edge_on_node(self.last_node.id), way_relations))
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
