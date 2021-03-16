#!/usr/bin/env python3
import numpy as np
from time import strftime, gmtime
import cereal.messaging as messaging
from common.realtime import Ratekeeper
from selfdrive.mapd.lib.osm import OSM
from selfdrive.mapd.lib.geo import distance
from selfdrive.mapd.lib.WayCollection import WayCollection


QUERY_RADIUS = 3000  # mts
MIN_DISTANCE_FOR_NEW_QUERY = 1000  # mts
FULL_STOP_MAX_SPEED = 1.39  # m/s Max speed for considering car is stopped.

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
    self.last_gps_fix_timestamp = 0
    self.last_gps = None
    self.lat = None
    self.lon = None
    self.bearing = None
    self.accuracy = None
    self.bearingAccuracy = None
    self.last_fetch_location = None
    self.last_route_update_fix_timestamp = 0
    self.last_publish_fix_timestamp = 0

  @property
  def location(self):
    if self.lat is None or self.lon is None:
      return None
    return self.lat, self.lon

  def update_gps(self, sm):
    sock = 'gpsLocationExternal'
    if not sm.updated[sock] or not sm.valid[sock]:
      return

    log = sm[sock]
    self.last_gps = log

    # ignore the message if the fix is invalid
    if log.flags % 2 == 0:
      return

    self.last_gps_fix_timestamp = log.timestamp  # Unix TS. Milliseconds since January 1, 1970.
    self.lat = log.latitude
    self.lon = log.longitude
    self.bearing = log.bearingDeg
    self.accuracy = log.accuracy
    self.bearingAccuracy = log.bearingAccuracyDeg

    _debug('Mapd: ********* Got GPS fix'
           f'Pos: {self.lat}, {self.lon} +/- {self.accuracy} mts.\n'
           f'Bearing: {self.bearing} +/- {self.bearingAccuracy} deg.\n'
           f'timestamp: {strftime("%d-%m-%y %H:%M:%S", gmtime(self.last_gps_fix_timestamp * 1e-3))}'
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

  def update_route(self, sm):
    if self.way_collection is None or self.location is None or self.bearing is None:
      return

    if self.last_route_update_fix_timestamp == self.last_gps_fix_timestamp:
      # No new fix since last update
      return

    self.last_route_update_fix_timestamp = self.last_gps_fix_timestamp

    # Create the route if not existent or if it was generated by an older way collection
    if self.route is None or self.route.way_collection_id != self.way_collection.id:
      self.route = self.way_collection.get_route(self.location, self.bearing)
      _debug(f'Mapd *****: Route created: \n{self.route}\n********')
      return

    # Do not attempt to update the route if the car is going close to a full stop, as the bearing can start
    # jumping and creating unnecesary loosing of the route. Since the route update timestamp has been updated
    # a new liveMapDataDEPRECATED message will be published with the current values (which is desirable)
    if sm['carState'].vEgo < FULL_STOP_MAX_SPEED:
      _debug('Mapd *****: Route Not updated as car has Stopped ********')
      return

    self.route.update(self.location, self.bearing)
    if self.route.located:
      _debug(f'Mapd *****: Route updated: \n{self.route}\n********')
      return

    # if an old route did not mange to locate, attempt to regenerate form way collection.
    self.route = self.way_collection.get_route(self.location, self.bearing)
    _debug(f'Mapd *****: Failed to update location in route. Regenerated with route: \n{self.route}\n********')

  def publish(self, pm, sm):
    # Ensure we have a route currently located
    if self.route is None or not self.route.located:
      return

    # Ensure we have a route update since last publish
    if self.last_publish_fix_timestamp == self.last_route_update_fix_timestamp:
      return

    self.last_publish_fix_timestamp = self.last_route_update_fix_timestamp

    speed_limit = self.route.current_speed_limit
    next_speed_limit_section = self.route.next_speed_limit_section
    current_curvature = self.route.immediate_curvature
    curvatures_ahead = self.route._curvatures_ahead
    curvatures_ahead = np.array([]) if curvatures_ahead is None else curvatures_ahead
    next_subst_curvature = self.route.next_substantial_curvature

    map_data_msg = messaging.new_message('liveMapDataDEPRECATED')
    map_data_msg.valid = sm.all_alive_and_valid(service_list=['gpsLocationExternal'])
    map_data_msg.liveMapDataDEPRECATED.lastGps = self.last_gps
    map_data_msg.liveMapDataDEPRECATED.speedLimitValid = bool(speed_limit is not None)
    map_data_msg.liveMapDataDEPRECATED.speedLimit = float(speed_limit if speed_limit is not None else 0.0)
    map_data_msg.liveMapDataDEPRECATED.speedLimitAheadValid = bool(next_speed_limit_section is not None)
    map_data_msg.liveMapDataDEPRECATED.speedLimitAhead = float(next_speed_limit_section.value
                                                               if next_speed_limit_section is not None else 0.0)
    map_data_msg.liveMapDataDEPRECATED.speedLimitAheadDistance = float(next_speed_limit_section.start
                                                                       if next_speed_limit_section is not None else 0.0)
    map_data_msg.liveMapDataDEPRECATED.curvatureValid = bool(current_curvature is not None)
    map_data_msg.liveMapDataDEPRECATED.curvature = float(current_curvature if current_curvature is not None else 0.0)
    map_data_msg.liveMapDataDEPRECATED.roadCurvatureX = [float(c[0]) for c in curvatures_ahead]
    map_data_msg.liveMapDataDEPRECATED.roadCurvature = [float(c[1]) for c in curvatures_ahead]
    map_data_msg.liveMapDataDEPRECATED.distToTurn = float(next_subst_curvature[0] 
                                                          if next_subst_curvature is not None else 0.0)

    pm.send('liveMapDataDEPRECATED', map_data_msg)
    _debug(f'Mapd *****: Publish: \n{map_data_msg}\n********')


# provides live map data information
def mapd_thread(sm=None, pm=None):
  mapd = MapD()
  rk = Ratekeeper(1., print_delay_threshold=None)  # Keeps rate at 1 hz

  # *** setup messaging
  if sm is None:
    sm = messaging.SubMaster(['gpsLocationExternal', 'carState'])
  if pm is None:
    pm = messaging.PubMaster(['liveMapDataDEPRECATED'])

  while True:
    sm.update()
    mapd.update_gps(sm)
    mapd.updated_osm_data()
    mapd.update_route(sm)
    mapd.publish(pm, sm)
    rk.keep_time()


def main(sm=None, pm=None):
  mapd_thread(sm, pm)


if __name__ == "__main__":
  main()
