import QtQuick 2.9
import QtLocation 5.9
import QtPositioning 5.9

Map {
  plugin: Plugin {
    name: "mapboxgl"
    PluginParameter { name: "mapboxgl.mapping.use_fbo"; value: "false" }
  }

  id: map

  // TODO: is there a better way to make map text bigger?
  width: 256
  height: 256
  scale: 2.5
  x: width * (scale-1)
  y: height * (scale-1)
  transformOrigin: Item.BottomRight

  center: QtPositioning.coordinate()
  zoomLevel: 16
  visible: center.isValid

  property variant carPosition: QtPositioning.coordinate()
  property real carBearing: 0;
  property bool nightMode: true;

  onSupportedMapTypesChanged: {
    activeMapType = Array.from(supportedMapTypes)
      .find(t => t.style === MapType.CarNavigationMap && t.night == nightMode)
  }

  MapQuickItem {
    id: car
    visible: carPosition.isValid && map.zoomLevel > 10
    anchorPoint.x: icon.width/2
    anchorPoint.y: icon.height/2

    coordinate: carPosition
    rotation: carBearing

    sourceItem: Image {
      id: icon
      source: "arrow-" + (map.nightMode ? "night" : "day") + ".svg"
      width: 60 / map.scale
      height: 60 / map.scale
    }
  }
}
