from selfdrive.mapd.lib.WayRelation import WayRelation
from selfdrive.mapd.lib.Route import Route
import uuid


_ACCEPTABLE_BEARING_DELTA_IND = 0.7071067811865475  # sin(pi/4) | 45 degrees acceptable bearing delta


class WayCollection():
  """A collection of WayRelations to use for maps data analysis.
  """
  def __init__(self, ways):
    self.id = uuid.uuid4()
    self.way_relations = list(map(lambda way: WayRelation(way), ways))

  def get_route(self, location, bearing):
    """Provides the best route found in the way collection based on provided `location` and `bearing`
    """
    if location is None or bearing is None:
      return None

    # Update all way relations in collection to the provided location and bearing.
    for wr in self.way_relations:
      wr.update(location, bearing)

    # Get the way relations where a match was found. i.e. those now marked as active.
    active_way_relations = list(filter(lambda wr: wr.active, self.way_relations))

    # If no active, then we could not find a current way to build a route.
    if len(active_way_relations) == 0:
      return None

    # If only one active, then pick it as current.
    if len(active_way_relations) == 1:
      current = active_way_relations[0]

    # If more than one is active, filter out any active way relation where the bearing delta indicator is too high.
    else:
      wr_acceptable_bearing = list(filter(lambda wr: wr.active_bearing_delta <= _ACCEPTABLE_BEARING_DELTA_IND, 
                                          active_way_relations))

      # If delta bearing indicator is too high for all, then use as current the one that has the shorter one.
      if len(wr_acceptable_bearing) == 0:
        active_way_relations.sort(key=lambda wr: wr.active_bearing_delta)
        current = active_way_relations[0]

      # If only one with acceptable bearing, use it.
      elif len(wr_acceptable_bearing) == 1:
        current = wr_acceptable_bearing[0]

      # If more than one with acceptable bearing, then now choose the closest one to the way
      else:
        wr_acceptable_bearing.sort(key=lambda wr: wr.distance_to_way)
        current = wr_acceptable_bearing[0]

    # Reset location for the remaining located way relations
    for wr in active_way_relations:
      if wr.id != current.id:
        wr.reset_location_variables()

    return Route(current, self.way_relations, self.id)
