#!/usr/bin/env python3
from cereal import car
from selfdrive.config import Conversions as CV
from selfdrive.car.mazda.values import CAR, LKAS_LIMITS
from selfdrive.car import STD_CARGO_KG, scale_rot_inertia, scale_tire_stiffness, gen_empty_fingerprint
from selfdrive.car.interfaces import CarInterfaceBase

ButtonType = car.CarState.ButtonEvent.Type
EventName = car.CarEvent.EventName

class CarInterface(CarInterfaceBase):

  @staticmethod
  def compute_gb(accel, speed):
    return float(accel) / 4.0

  @staticmethod
  def get_params(candidate, fingerprint=gen_empty_fingerprint(), car_fw=None):
    ret = CarInterfaceBase.get_std_params(candidate, fingerprint)

    ret.carName = "mazda"
    ret.safetyModel = car.CarParams.SafetyModel.mazda

    ret.dashcamOnly = True

    ret.radarOffCan = True

    ret.steerActuatorDelay = 0.1
    ret.steerRateCost = 1.0
    ret.steerLimitTimer = 0.8
    tire_stiffness_factor = 0.70   # not optimized yet

    if candidate == CAR.CX5:
      ret.mass = 3655 * CV.LB_TO_KG + STD_CARGO_KG
      ret.wheelbase = 2.7
      ret.steerRatio = 15.5
      ret.lateralTuning.pid.kiBP, ret.lateralTuning.pid.kpBP, ret.lateralTuning.pid.kfBP = [[0.], [0.], [0.]]
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.19], [0.019]]
      ret.lateralTuning.pid.kfV = [0.00006]
    elif candidate == CAR.CX9:
      ret.mass = 4217 * CV.LB_TO_KG + STD_CARGO_KG
      ret.wheelbase = 3.1
      ret.steerRatio = 17.6
      ret.lateralTuning.pid.kiBP, ret.lateralTuning.pid.kpBP, ret.lateralTuning.pid.kfBP = [[0.], [0.], [0.]]
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.19], [0.019]]
      ret.lateralTuning.pid.kfV = [0.00006]
    elif candidate == CAR.Mazda3:
      ret.mass = 2875 * CV.LB_TO_KG + STD_CARGO_KG
      ret.wheelbase = 2.7
      ret.steerRatio = 14.0
      ret.lateralTuning.pid.kiBP, ret.lateralTuning.pid.kpBP, ret.lateralTuning.pid.kfBP = [[0.], [0.], [0.]]
      ret.lateralTuning.pid.kpV, ret.lateralTuning.pid.kiV = [[0.19], [0.019]]
      ret.lateralTuning.pid.kfV = [0.00006]

    # No steer below disable speed
    ret.minSteerSpeed = LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS

    ret.centerToFront = ret.wheelbase * 0.41

    # TODO: get actual value, for now starting with reasonable value for
    # civic and scaling by mass and wheelbase
    ret.rotationalInertia = scale_rot_inertia(ret.mass, ret.wheelbase)

    # TODO: start from empirically derived lateral slip stiffness for the civic and scale by
    # mass and CG position, so all cars will have approximately similar dyn behaviors
    ret.tireStiffnessFront, ret.tireStiffnessRear = scale_tire_stiffness(ret.mass, ret.wheelbase, ret.centerToFront,
                                                                         tire_stiffness_factor=tire_stiffness_factor)

    ret.enableCamera = True

    return ret

  # returns a car.CarState
  def update(self, c, can_strings):

    self.cp.update_strings(can_strings)
    self.cp_cam.update_strings(can_strings)

    ret = self.CS.update(self.cp, self.cp_cam)
    ret.canValid = self.cp.can_valid and self.cp_cam.can_valid

    # events
    events = self.create_common_events(ret)

    if self.CS.low_speed_lockout:
      events.add(EventName.belowEngageSpeed)

    if self.CS.low_speed_alert:
      events.add(EventName.belowSteerSpeed)

    ret.events = events.to_msg()

    self.CS.out = ret.as_reader()
    return self.CS.out

  def apply(self, c):
    can_sends = self.CC.update(c.enabled, self.CS, self.frame, c.actuators)
    self.frame += 1
    return can_sends
