import QtQuick 2.9
import QtLocation 5.9
import QtPositioning 5.9
import "cheap-ruler.js" as CheapRuler

Item {
  id: app
  width: 640
  height: 640

  property variant carPosition: QtPositioning.coordinate()
  property real carBearing: 0
  property bool nightMode: mapPlugin.name != "osm"
  property bool satelliteMode: false
  property bool mapFollowsCar: true
  property bool lockedToNorth: false
  property variant ruler: CheapRuler.cheapRuler(raleigh.coordinate.latitude)

  Location {
    id: spartanburg
    coordinate: QtPositioning.coordinate(34.9495979, -81.9321125)
  }

  Location {
    id: raleigh
    coordinate: QtPositioning.coordinate(35.7796662, -78.6386822)
  }

  function coordinateToPoint(coordinate) {
    return [coordinate.longitude, coordinate.latitude]
  }

  // animation durations for continuously updated values shouldn't be much greater than updateInterval
  // ...otherwise, animations are always trying to catch up as their target values change
  property real updateInterval: 100

  Plugin {
    id: mapPlugin

    name: "osm"
    PluginParameter { name: "osm.mapping.cache.directory"; value: "/tmp/tile_cache" }
    PluginParameter { name: "osm.mapping.host"; value: "https://c.tile.openstreetmap.org" }
    PluginParameter { name: "osm.mapping.highdpi_tiles"; value: "true" }

    // TODO not availble on NEOS yet
    // name: "mapboxgl"
    // PluginParameter { name: "mapboxgl.access_token"; value: mapboxAccessToken }
    // PluginParameter { name: "mapboxgl.mapping.use_fbo"; value: "false" }
    // PluginParameter { name: "mapboxgl.mapping.cache.directory"; value: "/tmp/tile_cache" }
    // // necessary to draw route paths underneath road labels 
    // PluginParameter { name: "mapboxgl.mapping.items.insert_before"; value: "road-label-small" }
  }

  Plugin {
    id: routePlugin
    name: "mapbox"
    // routing requires valid access_token
    PluginParameter { name: "mapbox.access_token"; value: mapboxAccessToken }
  }

  onCarPositionChanged: {
    if (mapFollowsCar) {
      map.center = carPosition
    }
  }

  onCarBearingChanged: {
    if (mapFollowsCar && !lockedToNorth) {
      map.bearing = carBearing
    }
  }

  Map {
    id: map
    plugin: mapPlugin

    // TODO is there a better way to make map text bigger?
    width: parent.width / scale
    height: parent.height / scale
    scale: 2.5
    x: width * (scale - 1)
    y: height * (scale - 1)
    transformOrigin: Item.BottomRight

    gesture.enabled: true
    center: QtPositioning.coordinate()
    bearing: 0
    zoomLevel: 16
    copyrightsVisible: false // TODO re-enable

    // keep in sync with car indicator
    // TODO commonize with car indicator
    Behavior on center {
      CoordinateAnimation {
        easing.type: Easing.Linear;
        duration: updateInterval;
      }
    }

    Behavior on bearing {
      RotationAnimation {
        direction: RotationAnimation.Shortest
        easing.type: Easing.InOutQuad
        duration: updateInterval
      }
    }

    // TODO combine with center animation
    Behavior on zoomLevel {
      SmoothedAnimation {
        velocity: 2;
      }
    }

    onSupportedMapTypesChanged: {
      function score(mapType) {
        // prioritize satelliteMode over nightMode
        return (mapType.style === (satelliteMode ? MapType.HybridMap : MapType.CarNavigationMap)) << 1
            + (mapType.night === nightMode) << 0
      }
      activeMapType = Array.from(supportedMapTypes).sort((a, b) => score(b)-score(a))[0]
    }

    onBearingChanged: {
    }

    gesture.onPanStarted: {
      mapFollowsCar = false
    }

    gesture.onPinchStarted: {
      mapFollowsCar = false
    }

    MapItemView {
      id: route
      model: routeModel

      delegate: MapRoute {
        route: routeData
        line.color: "#ec0f73"
        line.width: map.zoomLevel - 5
        opacity: (index == 0) ? 0.8 : 0.3

        onRouteChanged: {
          // console.log("route changed:", JSON.stringify(routeData.segments, null, 2))
        }
      }
    }

    MapQuickItem {
      id: car
      visible: carPosition.isValid //&& map.zoomLevel > 10
      anchorPoint.x: icon.width / 2
      anchorPoint.y: icon.height / 2

      opacity: 0.8
      coordinate: carPosition
      rotation: carBearing - map.bearing

      Behavior on coordinate {
        CoordinateAnimation {
          easing.type: Easing.Linear;
          duration: updateInterval;
        }
      }

      sourceItem: Image {
        id: icon
        source: "arrow-" + (app.nightMode ? "night" : "day") + ".svg"
        width: 60 / map.scale
        height: 60 / map.scale
      }
    }
  }

  Column {
    id: buttons
    anchors.left: parent.left
    anchors.bottom: parent.bottom

    MouseArea {
      id: compass
      // visible: !lockedToNorth && !mapFollowsCar // TODO
      width: 125
      height: 113
      onClicked: {
        lockedToNorth = !lockedToNorth
        map.bearing = lockedToNorth || !mapFollowsCar ? 0 : carBearing
      }
      // Rectangle { anchors.fill: parent; color: 'transparent'; border.color: 'red'; border.width: 1; } // DEBUG
      Image {
        source: "compass.png"
        rotation: map.bearing
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 5
        width: 75
        height: 75

        scale: compass.pressed ? 0.85 : 1.0
        Behavior on scale { NumberAnimation { duration: 100 } }
      }
    }

    MouseArea {
      id: location
      width: 125
      height: 113
      onClicked: {
        if (carPosition.isValid) {
          mapFollowsCar = !mapFollowsCar
          if (mapFollowsCar) {
            lockedToNorth = false
            map.zoomLevel = 16
            map.center = carPosition
            map.bearing = carBearing
          }
        }
      }
      // Rectangle { anchors.fill: parent; color: 'transparent'; border.color: 'yellow'; border.width: 1; } // DEBUG
      Image {
        source: mapFollowsCar && carPosition.isValid ? "location-active.png" : "location.png"
        opacity: mapFollowsCar && carPosition.isValid ? 0.5 : 1.0
        width: 63
        height: 63
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -5

        scale: location.pressed ? 0.85 : 1.0
        Behavior on scale { NumberAnimation { duration: 100 } }
      }
    }
  }

  Text {
    id: instructions
    anchors.top: parent.top
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.margins: 20

    font.family: "Inter"
    font.pixelSize: 40
    color: nightMode ? "white" : "black"

    text: "Directions might go here"
  }

  RouteQuery {
    id: routeQuery
  }

  function updateRoute() {
    console.log("Updating route")
    routeQuery.clearWaypoints();
    routeQuery.addWaypoint(spartanburg.coordinate);
    routeQuery.addWaypoint(raleigh.coordinate);
    routeModel.update()
  }

  RouteModel {
    id: routeModel
    plugin: routePlugin
    query: routeQuery

    Component.onCompleted: {
      updateRoute()
    }
  }
}