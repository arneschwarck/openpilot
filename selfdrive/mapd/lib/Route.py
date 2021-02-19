from .NodesData import NodesData, NodeDataIdx
import numpy as np


_DISTANCE_LIMIT_FOR_CURRENT_CURVATURE = 20.  # mts
_SUBSTANTIAL_CURVATURE_THRESHOLD = 0.003  # 333 mts radius


class Route():
  """A set of consecutive way relations forming a default driving route.
  """
  def __init__(self, current, way_relations, way_collection_id):
    self.way_collection_id = way_collection_id
    self._ordered_way_relations = []
    self._nodes_data = None
    self._reset()

    # An active current way is needed to be able to build a route
    if not current.active:
      return

    # We need a ref or a name to build a route.
    ref = current.ref
    name = current.name
    # TODO: consider allowing to build a route when no ref or name is available.
    # be aware of the time taken to search for matching ways as we build the route.
    if ref is None and name is None:
      return

    # Reduce way relations to those matching the ref or name of the current one.
    way_relations = list(filter(lambda wr: wr.has_name_or_ref(name, ref), way_relations))

    # Build the ordered way relations list by recursively finding the next wr.
    wr = current
    while wr is not None:
      self._ordered_way_relations.append(wr)
      wr, way_relations = wr.next_wr(way_relations)

    # Build the node data from the ordered list of way relations
    self._nodes_data = NodesData(self._ordered_way_relations)

    # Locate where we are in the route node list.
    self._locate()

  def __repr__(self):
    count = self._nodes_data.count if self._nodes_data is not None else None
    return f'Route: {self.way_collection_id}, idx ahead: {self._ahead_idx} of {count}'

  def _reset(self):
    self._limits_ahead = None
    self._cuvature_limits_ahead = None
    self._curvatures_ahead = None
    self._ahead_idx = None
    self._distance_to_node_ahead = None

  @property
  def located(self):
    return self._ahead_idx is not None

  def _locate(self):
    """Will resolve the index in the nodes_data list for the node ahead of the current location.
    It updates as well the distance from the current location to the node ahead.
    """
    current = self.current_wr
    if current is None:
      return

    node_ahead_id = current.node_ahead.id
    self._distance_to_node_ahead = current.distance_to_node_ahead
    start_idx = self._ahead_idx if self._ahead_idx is not None else 1
    self._ahead_idx = None

    ids = self._nodes_data.get(NodeDataIdx.node_id)
    for idx in range(start_idx, len(ids)):
      if ids[idx] == node_ahead_id:
        self._ahead_idx = idx
        break

  @property
  def valid(self):
    return self.current_wr is not None

  @property
  def current_wr(self):
    return self._ordered_way_relations[0] if len(self._ordered_way_relations) else None

  def update(self, location, bearing):
    """Will update the route structure based on the given `location` and `bearing` assuming progress on the route
    on the original direction. If direction has changed or active point on the route can not be found, the route
    will become invalid.
    """
    if len(self._ordered_way_relations) == 0 or location is None or bearing is None:
      return

    # Skip if no update on location or bearing.
    if self.current_wr.location == location and self.current_wr.bearing == bearing:
      return

    # Transverse the way relations on the actual order until we find an active one. From there, rebuild the route
    # with the way relations remaining ahead.
    for idx, wr in enumerate(self._ordered_way_relations):
      active_direction = wr.direction
      wr.update(location, bearing)

      if not wr.active:
        continue

      if wr.direction == active_direction:
        # We have now the current wr. Repopulate from here till the end and locate
        self._ordered_way_relations = self._ordered_way_relations[idx:]
        self._reset()
        self._locate()
        return

      # Driving direction on the route has changed. stop.
      break

    # if we got here, there is no new active way relation or driving direction has changed. Reset.
    self._reset()

  @property
  def speed_limits_ahead(self):
    """Returns and array of SpeedLimitSection objects for the actual route ahead of current location
    """
    if self._limits_ahead is not None:
      return self._limits_ahead

    if self._nodes_data is None or self._ahead_idx is None:
      return []

    self._limits_ahead = self._nodes_data.speed_limits_ahead(self._ahead_idx, self._distance_to_node_ahead)
    return self._limits_ahead

  @property
  def curvature_speed_limits_ahead(self):
    """Returns and array of SpeedLimitSection objects for the actual route ahead of current location due to curvatures
    """
    if self._cuvature_limits_ahead is not None:
      return self._cuvature_limits_ahead

    if self._nodes_data is None or self._ahead_idx is None:
      return []

    self._cuvature_limits_ahead = self._nodes_data. \
        curvatures_speed_limit_sections_ahead(self._ahead_idx, self._distance_to_node_ahead)

    return self._cuvature_limits_ahead

  @property
  def current_speed_limit(self):
    if not self.located:
      return None

    limits_ahead = self.speed_limits_ahead
    if not len(limits_ahead) or limits_ahead[0].start != 0:
      return None

    return limits_ahead[0].value

  @property
  def current_curvature_speed_limit(self):
    if not self.located:
      return None

    limits_ahead = self.curvature_speed_limits_ahead
    if not len(limits_ahead) or limits_ahead[0].start != 0:
      return None

    return limits_ahead[0].value

  @property
  def next_speed_limit_section(self):
    if not self.located:
      return None

    limits_ahead = self.speed_limits_ahead
    if not len(limits_ahead):
      return None

    # Find the first section that does not start in 0. i.e. the next section
    for section in limits_ahead:
      if section.start > 0:
        return section

    return None

  @property
  def next_curvature_speed_limit_section(self):
    if not self.located:
      return None

    limits_ahead = self.curvature_speed_limits_ahead
    if not len(limits_ahead):
      return None

    return limits_ahead[0]

  @property
  def curvatures_ahead(self):
    """Provides a list of ordered pairs by distance including the distance ahead and the curvature.
    """
    if not self.located or self._nodes_data is None:
      return None

    if self._curvatures_ahead is not None:
      return self._curvatures_ahead

    self._curvatures_ahead = self._nodes_data.curvatures_ahead(self._ahead_idx, self._distance_to_node_ahead)
    return self._curvatures_ahead

  @property
  def immediate_curvature(self):
    """Provides the highest curvature value in the immediate region ahead.
    """
    if not self.located:
      return None

    curvatures_ahead = self.curvatures_ahead
    if not len(curvatures_ahead):
      return None

    immediate_curvatures = curvatures_ahead[curvatures_ahead[:, 0] <= _DISTANCE_LIMIT_FOR_CURRENT_CURVATURE]
    if not len(immediate_curvatures):
      return None

    return np.max(immediate_curvatures[:, 1])

  @property
  def max_curvature_ahead(self):
    """Provides the maximum curvature on route ahead
    """
    if not self.located:
      return None

    curvatures_ahead = self.curvatures_ahead
    if not len(curvatures_ahead):
      return None

    return np.max(curvatures_ahead[:, 1])

  @property
  def next_substantial_curvature(self):
    """Provides the next substantial curvature and the distance to it.
    """
    if not self.located:
      return None

    curvatures_ahead = self.curvatures_ahead
    if not len(curvatures_ahead):
      return None

    filt = np.logical_and(curvatures_ahead[:, 0] > _DISTANCE_LIMIT_FOR_CURRENT_CURVATURE,
                          curvatures_ahead[:, 1] > _SUBSTANTIAL_CURVATURE_THRESHOLD)
    substantial_curvatures_ahead = curvatures_ahead[filt]

    if not len(substantial_curvatures_ahead):
      return None

    return substantial_curvatures_ahead[0, :]

  @property
  def distance_to_end(self):
    if not self.located:
      return None

    return self._nodes_data.distance_to_end(self._ahead_idx, self._distance_to_node_ahead)
