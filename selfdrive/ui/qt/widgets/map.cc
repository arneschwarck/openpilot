#include <cassert>

#include <QGeoCoordinate>
#include <QQmlContext>
#include <QQmlProperty>
#include <QQuickWidget>
#include <QQuickView>
#include <QStackedLayout>
#include <QVariant>

#include "common/util.h"
#include "map.hpp"
// #include "mapManager.hpp"

#if defined(QCOM) || defined(QCOM2)
const std::string mapbox_access_token_path = "/persist/mapbox/access_token";
#else
const std::string mapbox_access_token_path = util::getenv_default("HOME", "/.comma/persist/mapbox/access_token", "/persist/mapbox/access_token");
#endif

QtMap::QtMap(QWidget *parent) : QFrame(parent) {
  QStackedLayout* layout = new QStackedLayout();

  auto file = QFile(mapbox_access_token_path.c_str());
  assert(file.open(QIODevice::ReadOnly));
  auto mapboxAccessToken = file.readAll();
  qDebug() << "Mapbox access token:" << mapboxAccessToken;

  // might have to use QQuickWidget for proper stacking?
  QQuickWidget *map = new QQuickWidget();
  map->rootContext()->setContextProperty("mapboxAccessToken", mapboxAccessToken);
  map->setSource(QUrl::fromLocalFile("qt/widgets/map.qml"));
  mapObject = map->rootObject();
  QSize size = map->size();

  // using QQuickView seems to make other ui drawing break (eg. video is all black) - maybe need resetOpenGLState()?
  // QQuickView *mapView = new QQuickView();
  // mapView->setSource(QUrl::fromLocalFile("qt/widgets/map.qml"));
  // QSize size = mapView->size();
  // map = QWidget::createWindowContainer(mapView, this);
  // mapObject = mapView->rootObject();

  // TODO focus stuff needed? https://www.qtdeveloperdays.com/sites/default/files/Adding%20QtQuick%20base%20windows%20to%20an%20existing%20QWidgets%20Application-dark.pdf
  // setFocusProxy(map); // focus container widget when top level widget is focused
  // setFocusPolicy(Qt::NoFocus); // work around QML activation issue

  QSizeF scaledSize = mapObject->size() * mapObject->scale();
  qDebug() << "size" << size;
  qDebug() << "scaledSize" << scaledSize;
  qDebug() << "mapObject->scale()" << mapObject->scale();
  map->setFixedSize(scaledSize.toSize());
  setFixedSize(scaledSize.toSize());

  layout->addWidget(map);
  setLayout(layout);

  // Start polling loop
  sm = new SubMaster({"gpsLocationExternal"});
  timer.start(100, this); // 10Hz

  // QObject::connect(map, SIGNAL(), parent, SLOT());
}

void QtMap::timerEvent(QTimerEvent *event) {
  if (!event)
    return;

  if (event->timerId() == timer.timerId()) {
    if (isVisible())
      updatePosition();
  }
  else
    QObject::timerEvent(event);
}

void QtMap::updatePosition() {
  if (sm->update(0) > 0) {
    if (sm->updated("gpsLocationExternal")) {
      cereal::GpsLocationData::Reader gps = (*sm)["gpsLocationExternal"].getGpsLocationExternal();
      float bearing = gps.getBearingDeg();
      QGeoCoordinate position = gps.getAccuracy() > 1000 ? QGeoCoordinate() : QGeoCoordinate(gps.getLatitude(), gps.getLongitude(), gps.getAltitude());
      QQmlProperty::write(mapObject, "carPosition", QVariant::fromValue(position));
      QQmlProperty::write(mapObject, "carBearing", bearing);
    }
  }
}