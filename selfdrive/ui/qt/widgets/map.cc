#include <QStackedLayout>
#include <QQuickView>

#include "map.hpp"

QtMap::QtMap(QWidget *parent) : QWidget(parent) {
  QStackedLayout* layout = new QStackedLayout();

  QQuickView *mapView = new QQuickView();
  mapView->setSource(QUrl::fromLocalFile("qt/widgets/map.qml"));
  map = QWidget::createWindowContainer(mapView);

  map->setFixedSize(512, 512);
  layout->addWidget(map);

  setLayout(layout);

  // QObject::connect(map, SIGNAL(), parent, SLOT());
}