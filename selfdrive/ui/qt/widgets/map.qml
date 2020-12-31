import QtQuick 2.9
// import QtQuick.Window 2.3
import QtLocation 5.9
import QtPositioning 5.9

Map {
  plugin: Plugin {
    name: "mapboxgl"
    // DEVELOPMENT
    // PluginParameter { name: "mapboxgl.access_token"; value: "pk.eyJ1IjoicXRzZGsiLCJhIjoiY2l5azV5MHh5MDAwdTMybzBybjUzZnhxYSJ9.9rfbeqPjX2BusLRDXHCOBA" }
    PluginParameter { name: "mapboxgl.mapping.use_fbo"; value: "false" }
  }

  width: 512
  height: 512
  // anchors.centerIn: parent;
  // anchors.fill: parent

  center: QtPositioning.coordinate()
  zoomLevel: 16

  property variant carPosition: QtPositioning.coordinate()
  property real carBearing: 0;

  // activeMapType: MapType.CarNavigationMap

  MapQuickItem {
    id: car

    anchorPoint.x: icon.width/2
    anchorPoint.y: icon.height/2

    coordinate: carPosition
    rotation: carBearing
    // NumberAnimation on rotation { from: 0; to: 360; duration: 2000; loops: Animation.Infinite; }

    sourceItem: Rectangle {
      id: icon
      color: "darkgrey"
      width: 25
      height: 60
    }
  }
}
