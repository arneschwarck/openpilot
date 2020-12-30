#pragma once

#include <QWidget>

class QtMap : public QWidget {
  Q_OBJECT

public:
  explicit QtMap(QWidget* parent = 0);

private:
  QWidget* map;
};
