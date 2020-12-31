#include <QGeoCoordinate>
#include <QQmlProperty>
#include <QQuickWidget>
#include <QQuickView>
#include <QStackedLayout>
#include <QVariant>

#include "map.hpp"
// #include "mapManager.hpp"

QtMap::QtMap(QWidget *parent) : QWidget(parent) {
  QStackedLayout* layout = new QStackedLayout();

  // TODO might have to use this for stacking
  // QQuickWidget *map = new QQuickWidget();
  // map->setSource(QUrl::fromLocalFile("qt/widgets/map.qml"));
  // QSize size = map->size();

  QQuickView *mapView = new QQuickView();
  mapView->setSource(QUrl::fromLocalFile("qt/widgets/map.qml"));
  QSize size = mapView->size();
  map = QWidget::createWindowContainer(mapView, this);
  mapObject = mapView->rootObject();
  // TODO focus stuff needed? https://www.qtdeveloperdays.com/sites/default/files/Adding%20QtQuick%20base%20windows%20to%20an%20existing%20QWidgets%20Application-dark.pdf
  // setFocusProxy(map); // focus container widget when top level widget is focused
  // setFocusPolicy(Qt::NoFocus); // work around QML activation issue

  map->setFixedSize(size);
  setFixedSize(size);
  layout->addWidget(map);
  setLayout(layout);

  // Start polling loop
  sm = new SubMaster({"gpsLocationExternal"});
  timer.start(15, this);

  // QObject::connect(map, SIGNAL(), parent, SLOT());
}

void QtMap::timerEvent(QTimerEvent *event) {
  if (!event)
    return;

  if (event->timerId() == timer.timerId())
    updatePosition();
  else
    QObject::timerEvent(event);
}

void QtMap::updatePosition() {
  bool mapFollowsCar = true;
  bool lockedToNorth = false;

  if (sm->update(0) > 0) {
    if (sm->updated("gpsLocationExternal")) {
      cereal::GpsLocationData::Reader gps = (*sm)["gpsLocationExternal"].getGpsLocationExternal();
      float bearing = gps.getBearing();
      QVariant position = QVariant::fromValue(QGeoCoordinate(gps.getLatitude(), gps.getLongitude(), gps.getAltitude()));
      QQmlProperty::write(mapObject, "carPosition", position);
      QQmlProperty::write(mapObject, "carBearing", bearing);

      if (mapFollowsCar) {
        QQmlProperty::write(mapObject, "center", position);
        QQmlProperty::write(mapObject, lockedToNorth ? "bearing" : "carBearing", 0);
        QQmlProperty::write(mapObject, lockedToNorth ? "carBearing" : "bearing", bearing);
      }
      // qDebug()
      //  << "Bearing:" << QQmlProperty::read(mapObject, "carBearing").toFloat()
      //  << "| Position:" << posLong << posLat;
    }
  }
}