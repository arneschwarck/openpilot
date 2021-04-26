#!/usr/bin/env python3
from time import strftime, gmtime
import cereal.messaging as messaging
from common.realtime import Ratekeeper
from selfdrive.mapd.lib.osm import OSM
from selfdrive.mapd.lib.geo import distance
from selfdrive.mapd.lib.WayCollection import WayCollection


QUERY_RADIUS = 3000  # mts
MIN_DISTANCE_FOR_NEW_QUERY = 1000  # mts

_DEBUG = True


def _debug(msg):
  if not _DEBUG:
    return
  print(msg)


class MapD():
  def __init__(self):
    self.osm = OSM()
    self.way_collection = None
    self.route = None
    self.last_gps_fix_time = 0
    self.lat = None
    self.lon = None
    self.bearingDeg = None
    self.accuracy = None
    self.bearingAccuracy = None
    self.last_fetch_location = None
    self.last_route_update_time = 0
    self.last_publish_time = 0

  @property
  def location(self):
    if self.lat is None or self.lon is None:
      return None
    return self.lat, self.lon

  def update_gps(self, sm):
    sock = 'gpsLocationExternal'
    if not sm.updated[sock] or not sm.valid[sock]:
      return

    current_time = sm.logMonoTime[sock] * 1e-9
    log = sm[sock]

    # ignore the message if the fix is invalid
    if log.flags % 2 == 0:
      return

    self.last_gps_fix_time = current_time
    self.lat = log.latitude
    self.lon = log.longitude
    self.bearingDeg = log.bearingDeg
    self.accuracy = log.accuracy
    self.bearingAccuracy = log.bearingAccuracy

    _debug('Mapd: ********* Got GPS fix'
           f'Pos - Acc: {log.latitude}, {log.longitude} - {log.accuracy}.\n'
           f'bearingDeg - Acc: {log.bearingDeg} - {log.bearingAccuracy},\n'
           f'*******')

  def updated_osm_data(self):
    if self.route is not None:
      distance_to_end = self.route.distance_to_end
      if distance_to_end is not None and distance_to_end >= MIN_DISTANCE_FOR_NEW_QUERY:
        # do not query as long as we have a route with enough distance ahead.
        return

    if self.location is None:
      return

    if self.last_fetch_location is not None:
      distance_since_last = distance(self.location, self.last_fetch_location)
      if distance_since_last < QUERY_RADIUS - MIN_DISTANCE_FOR_NEW_QUERY:
        # do not query if are still not close to the border of previous query area
        return

    ways = self.osm.fetch_road_ways_around_location(self.location, QUERY_RADIUS)
    self.way_collection = WayCollection(ways)
    self.last_fetch_location = self.location

    _debug(f'Mapd: Updated map data @ {self.location} - got {len(ways)} ways')

  def update_route(self):
    if self.way_collection is None or self.location is None or self.bearingDeg is None:
      return

    if self.last_route_update_time == self.last_gps_fix_time:
      # No new fix since last update
      return

    self.last_route_update_time = self.last_gps_fix_time

    # Create the route if not existent or if it was generated by an older way collection
    if self.route is None or self.route.way_collection_id != self.way_collection.id:
      self.route = self.way_collection.get_route(self.location, self.bearingDeg)
    else:
      self.route.update(self.location, self.bearingDeg)
      # if an old route did not mange to locate, attempt to regenerate form way collection.
      if not self.route.located:
        self.route = self.way_collection.get_route(self.location, self.bearingDeg)

    _debug(f'Mapd *****: Route updated: \n{self.route}\n********')

  def publish(self, pm, sm):
    # Ensure we have a route currently located
    if self.route is None or not self.route.located:
      return

    # Ensure we have a route update since last publish
    if self.last_publish_time == self.last_route_update_time:
      return

    self.last_publish_time = self.last_route_update_time

    speed_limit = self.route.current_speed_limit
    next_speed_limit_section = self.route.next_speed_limit_section
    turn_speed_limit_section = self.route.current_curvature_speed_limit_section
    next_turn_speed_limit_section = self.route.next_curvature_speed_limit_section

    map_data_msg = messaging.new_message('liveMapData')
    map_data_msg.valid = sm.all_alive_and_valid(service_list=['gpsLocationExternal'])

    map_data_msg.liveMapData.lastGpsTimestamp = self.last_gps.timestamp
    map_data_msg.liveMapData.speedLimitValid = bool(speed_limit is not None)
    map_data_msg.liveMapData.speedLimit = float(speed_limit if speed_limit is not None else 0.0)
    map_data_msg.liveMapData.speedLimitAheadValid = bool(next_speed_limit_section is not None)
    map_data_msg.liveMapData.speedLimitAhead = float(next_speed_limit_section.value
                                                     if next_speed_limit_section is not None else 0.0)
    map_data_msg.liveMapData.speedLimitAheadDistance = float(next_speed_limit_section.start
                                                             if next_speed_limit_section is not None else 0.0)

    map_data_msg.liveMapData.turnSpeedLimitValid = bool(turn_speed_limit_section is not None)
    map_data_msg.liveMapData.turnSpeedLimit = float(turn_speed_limit_section.value
                                                    if turn_speed_limit_section is not None else 0.0)
    map_data_msg.liveMapData.turnSpeedLimitEndDistance = float(turn_speed_limit_section.end
                                                               if turn_speed_limit_section is not None else 0.0)
    map_data_msg.liveMapData.turnSpeedLimitAheadValid = bool(next_turn_speed_limit_section is not None)
    map_data_msg.liveMapData.turnSpeedLimitAhead = float(next_turn_speed_limit_section.value
                                                         if next_turn_speed_limit_section is not None else 0.0)
    map_data_msg.liveMapData.turnSpeedLimitAheadDistance = float(next_turn_speed_limit_section.start
                                                                 if next_turn_speed_limit_section is not None else 0.0)

    pm.send('liveMapData', map_data_msg)
    _debug(f'Mapd *****: Publish: \n{map_data_msg}\n********')


# provides live map data information
def mapd_thread(sm=None, pm=None):
  mapd = MapD()
  rk = Ratekeeper(1., print_delay_threshold=None)  # Keeps rate at 1 hz

  # *** setup messaging
  if sm is None:
    sm = messaging.SubMaster(['gpsLocationExternal'])
  if pm is None:
    pm = messaging.PubMaster(['liveMapData'])

  while True:
    sm.update()
    mapd.update_gps(sm)
    mapd.updated_osm_data()
    mapd.update_route()
    mapd.publish(pm, sm)
    rk.keep_time()


def main(sm=None, pm=None):
  mapd_thread(sm, pm)


if __name__ == "__main__":
  main()
