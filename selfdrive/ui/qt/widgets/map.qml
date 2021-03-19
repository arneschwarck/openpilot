import QtQuick 2.9
import QtLocation 5.9
import QtPositioning 5.9

Map {
  plugin: Plugin {
    name: "osm"
    PluginParameter { name: "osm.mapping.cache.directory"; value: "/tmp/tile_cache" }
    // name: "mapboxgl"
    // PluginParameter { name: "mapboxgl.mapping.use_fbo"; value: "false" }
    // PluginParameter { name: "mapboxgl.mapping.cache.directory"; value: "/tmp/tile_cache" }
  }

  id: map

  // TODO is there a better way to make map text bigger?
  width: 256
  height: 256
  scale: 2.5
  x: width * (scale-1)
  y: height * (scale-1)
  transformOrigin: Item.BottomRight

  gesture.enabled: true
  center: QtPositioning.coordinate()
  bearing: 100
  zoomLevel: 16
  copyrightsVisible: false // TODO re-enable

  property variant carPosition: QtPositioning.coordinate()
  property real carBearing: 0;
  property bool nightMode: true;
  property bool satelliteMode: false;
  property bool mapFollowsCar: true;
  property bool lockedToNorth: true

  onSupportedMapTypesChanged: {
    function score(mapType) {
      // prioritize satelliteMode over nightMode
      return 2 * (mapType.style === (satelliteMode ? MapType.HybridMap : MapType.CarNavigationMap))
            + (mapType.night === nightMode)
    }
    activeMapType = Array.from(supportedMapTypes).sort((a, b) => score(b)-score(a))[0]
  }

  onCarPositionChanged: {
    if (mapFollowsCar) {
      center = carPosition
    }
  }

  onCarBearingChanged: {
    if (mapFollowsCar && !lockedToNorth) {
      bearing = carBearing
    }
  }

  onBearingChanged: {
    // console.log("BEARING: " + bearing)
  }

  MouseArea {
    id: compass
    // visible: !lockedToNorth
    width: 50
    height: 45
    x: 0
    y: map.height - height - location.height
    onClicked: {
      // console.log("North-lock clicked")
      lockedToNorth = !lockedToNorth
        // TODO animate rotation and (maybe) compass visibility
      map.bearing = lockedToNorth ? 0 : carBearing
    }
    Image {
      source: "compass.png"
      rotation: map.bearing
      width: 30
      height: 30
      x: 7.5
      y: compass.height - height - 5
    }
  }

  MouseArea {
    id: location
    width: 50
    height: 45
    x: 0
    y: map.height - height
    onClicked: {
      if (carPosition.isValid) {
        // console.log("Location clicked")
        mapFollowsCar = !mapFollowsCar
        lockedToNorth = false
        // TODO animate rotation/translation
        // TODO zoom
        map.center = carPosition
        map.bearing = carBearing
      }
    }
    Image {
      source: mapFollowsCar && carPosition.isValid ? "location-active.png" : "location.png"
      opacity: mapFollowsCar && carPosition.isValid ? 0.5 : 1.0
      width: 25
      height: 25
      x: 10
      y: location.height - height - 10
    }
  }

  MapQuickItem {
    id: car
    visible: carPosition.isValid && map.zoomLevel > 10
    anchorPoint.x: icon.width/2
    anchorPoint.y: icon.height/2

    opacity: 0.8
    coordinate: carPosition
    rotation: carBearing - bearing

    sourceItem: Image {
      id: icon
      source: "arrow-" + (map.nightMode ? "night" : "day") + ".svg"
      width: 60 / map.scale
      height: 60 / map.scale
    }
  }
}
