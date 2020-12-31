import QtQuick 2.9
import QtLocation 5.9
import QtPositioning 5.9

Map {
  plugin: Plugin {
    name: "mapboxgl"
    // DEVELOPMENT
    // PluginParameter { name: "mapboxgl.access_token"; value: "pk.eyJ1IjoicXRzZGsiLCJhIjoiY2l5azV5MHh5MDAwdTMybzBybjUzZnhxYSJ9.9rfbeqPjX2BusLRDXHCOBA" }
    PluginParameter { name: "mapboxgl.mapping.use_fbo"; value: "false" }
  }

  id: map
  width: 512
  height: 512
  center: QtPositioning.coordinate()
  zoomLevel: 16
  visible: center.isValid

  property variant carPosition: QtPositioning.coordinate()
  property real carBearing: 0;

  // activeMapType: MapType.CarNavigationMap

  MapQuickItem {
    id: car
    visible: carPosition.isValid && map.zoomLevel > 10
    anchorPoint.x: icon.width/2
    anchorPoint.y: icon.height/2

    coordinate: carPosition
    rotation: carBearing

    sourceItem: Image {
      id: icon
      source: "arrow.svg"
      width: 60
      height: 60
    }
  }
}
