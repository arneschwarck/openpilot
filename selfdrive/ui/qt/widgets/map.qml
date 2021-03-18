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

  center: QtPositioning.coordinate(60.170448, 24.942046) // Helsinki
  zoomLevel: 12

  // activeMapType: MapType.CarNavigationMap

  MapParameter {
    type: "source"

    property var name: "routeSource"
    property var sourceType: "geojson"
    property var data: '{ "type": "FeatureCollection", "features": \
      [{ "type": "Feature", "properties": {}, "geometry": { \
      "type": "LineString", "coordinates": [[ 24.934938848018646, \
      60.16830257086771 ], [ 24.943315386772156, 60.16227776476442 ]]}}]}'
  }

  MapParameter {
    type: "layer"

    property var name: "route"
    property var layerType: "line"
    property var source: "routeSource"

    // Draw under the first road label layer
    // of the mapbox-streets style.
    property var before: "road-label-small"
  }

  MapParameter {
    type: "paint"

    property var layer: "route"
    property var lineColor: "blue"
    property var lineWidth: 8.0
  }

  MapParameter {
    type: "layout"

    property var layer: "route"
    property var lineJoin: "round"
    property var lineCap: "round"
  }
}