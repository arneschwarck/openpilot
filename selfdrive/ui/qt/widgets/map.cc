#include <cassert>

#include <QGeoCoordinate>
#include <QQmlProperty>
#include <QQuickWidget>
#include <QQuickView>
#include <QStackedLayout>
#include <QVariant>

#include "common/utilpp.h"
#include "map.hpp"
// #include "mapManager.hpp"

#if defined(QCOM) || defined(QCOM2)
const std::string mapbox_access_token_path = "/persist/mapbox/access_token";
#else
const std::string mapbox_access_token_path = util::getenv_default("HOME", "/.comma/persist/mapbox/access_token", "/persist/mapbox/access_token");
#endif

QtMap::QtMap(QWidget *parent) : QWidget(parent) {
  QStackedLayout* layout = new QStackedLayout();

  // might have to use this method for stacking
  QQuickWidget *map = new QQuickWidget();
  map->setSource(QUrl::fromLocalFile("qt/widgets/map.qml"));
  mapObject = map->rootObject();
  QSize size = map->size();
  // QSizeF scaledSize = QSizeF(512, 512);//mapObject->size() * 4.0;
  QSizeF scaledSize = mapObject->size() * mapObject->scale();
  // QSize scaledSize = (mapObject->size() * mapObject->scale()).toSize();
  qDebug() << "size" << size;
  qDebug() << "scaledSize" << scaledSize;
  qDebug() << "mapObject->scale()" << mapObject->scale();

  // using this method seems to make other ui drawing break (eg. video is all black)
  // QQuickView *mapView = new QQuickView();
  // mapView->setSource(QUrl::fromLocalFile("qt/widgets/map.qml"));
  // QSize size = mapView->size();
  // map = QWidget::createWindowContainer(mapView, this);
  // mapObject = mapView->rootObject();
  // TODO focus stuff needed? https://www.qtdeveloperdays.com/sites/default/files/Adding%20QtQuick%20base%20windows%20to%20an%20existing%20QWidgets%20Application-dark.pdf
  // setFocusProxy(map); // focus container widget when top level widget is focused
  // setFocusPolicy(Qt::NoFocus); // work around QML activation issue

  // map->setFixedSize(scaledSize.toSize());
  // mapObject->setSize(scaledSize);
  // setFixedSize(scaledSize.toSize());
  map->setFixedSize(scaledSize.toSize());
  // mapObject->cale(2.0);
  // mapObject->setX(256);
  // mapObject->setY(256);
  // mapObject->setSize(QSizeF(256, 256));
  setFixedSize(scaledSize.toSize());

  layout->addWidget(map);
  setLayout(layout);

  // Configure mapbox
  auto file = QFile(mapbox_access_token_path.c_str());
  assert(file.open(QIODevice::ReadOnly));
  auto mapboxAccessToken = file.readAll();
  qDebug() << "Access token:" << mapboxAccessToken;

  QVariantMap parameters;
  parameters["mapboxgl.access_token"] = mapboxAccessToken;
  parameters[QStringLiteral("osm.useragent")] = QStringLiteral("QtLocation Mapviewer example");
  // QMetaObject::invokeMethod(mapObject, "initializeProviders",
  //                           Q_ARG(QVariant, QVariant::fromValue(parameters)));

  // Start polling loop
  sm = new SubMaster({"gpsLocationExternal"});
  timer.start(100, this); // 10Hz

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
  bool lockedToNorth = true;

  if (sm->update(0) > 0) {
    if (sm->updated("gpsLocationExternal")) {
      cereal::GpsLocationData::Reader gps = (*sm)["gpsLocationExternal"].getGpsLocationExternal();
      float bearing = gps.getBearing();
      QGeoCoordinate position = gps.getAccuracy() > 1000 ? QGeoCoordinate() : QGeoCoordinate(gps.getLatitude(), gps.getLongitude(), gps.getAltitude());
      QQmlProperty::write(mapObject, "carPosition", QVariant::fromValue(position));
      QQmlProperty::write(mapObject, "carBearing", bearing);

      if (mapFollowsCar) {
        QQmlProperty::write(mapObject, "center", QVariant::fromValue(position));
        QQmlProperty::write(mapObject, lockedToNorth ? "bearing" : "carBearing", 0);
        QQmlProperty::write(mapObject, lockedToNorth ? "carBearing" : "bearing", bearing);
      }
      // qDebug()
      //  << "Bearing:" << QQmlProperty::read(mapObject, "carBearing").toFloat()
      //  << "| Position:" << posLong << posLat;
    }
  }
}