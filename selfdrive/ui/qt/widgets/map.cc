#include <QQuickWidget>
#include <QQuickView>
#include <QStackedLayout>

#include "map.hpp"

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
  // TODO focus stuff needed? https://www.qtdeveloperdays.com/sites/default/files/Adding%20QtQuick%20base%20windows%20to%20an%20existing%20QWidgets%20Application-dark.pdf
  // setFocusProxy(map); // focus container widget when top level widget is focused
  // setFocusPolicy(Qt::NoFocus); // work around QML activation issue

  map->setFixedSize(size);
  setFixedSize(size);
  layout->addWidget(map);
  setLayout(layout);

  // QObject::connect(map, SIGNAL(), parent, SLOT());
}