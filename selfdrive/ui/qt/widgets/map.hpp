#pragma once

#include <QBasicTimer>
#include <QQuickItem>
#include <QWidget>
#include "messaging.hpp"

class QtMap : public QWidget {
  Q_OBJECT

public:
  explicit QtMap(QWidget* parent = 0);

protected:
  void timerEvent(QTimerEvent *event) override;

private:
  SubMaster *sm;
  QWidget *map;
  QQuickItem *mapObject;
  QBasicTimer timer;
  int i = 0;

  void updatePosition();
};
