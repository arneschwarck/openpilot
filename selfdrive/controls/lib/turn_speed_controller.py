import numpy as np
import time
from common.params import Params
from cereal import log
from common.realtime import sec_since_boot
from selfdrive.controls.lib.speed_smoother import speed_smoother

_LON_MPC_STEP = 0.2  # Time stemp of longitudinal control (5 Hz)

_MIN_ADAPTING_BRAKE_ACC = -1.5  # Minimum acceleration allowed when adapting to lower speed limit.
_MIN_ADAPTING_BRAKE_JERK = -1.0  # Minimum jerk allowed when adapting to lower speed limit.
_SPEED_OFFSET_TH = -3.0  # m/s Maximum offset between speed limit and current speed for adapting state.
_LIMIT_ADAPT_TIME_PER_MS = 1.8  # Ideal adapt time(s) to lower speed limit. i.e. braking for every m/s of speed delta.
_MIN_LIMIT_ADAPT_TIME = 5.  # s, Minimum time to provide for adapting logic.

_MAX_MAP_DATA_AGE = 10.0  # s Maximum time to hold to map data, then consider it invalid.

_DEBUG = False

TurnSpeedControlState = log.ControlsState.SpeedLimitControlState


def _debug(msg):
  if not _DEBUG:
    return
  print(msg)


def _description_for_state(turn_speed_control_state):
  if turn_speed_control_state == TurnSpeedControlState.inactive:
    return 'INACTIVE'
  if turn_speed_control_state == TurnSpeedControlState.adapting:
    return 'ADAPTING'
  if turn_speed_control_state == TurnSpeedControlState.active:
    return 'ACTIVE'


class TurnSpeedController():
  def __init__(self):
    self._params = Params()
    self._last_params_update = 0.0
    self._is_enabled = self._params.get("TurnSpeedControl", encoding='utf8') == "1"
    self._op_enabled = False
    self._active_jerk_limits = [0.0, 0.0]
    self._active_accel_limits = [0.0, 0.0]
    self._adapting_jerk_limits = [_MIN_ADAPTING_BRAKE_JERK, 1.0]
    self._v_ego = 0.0
    self._a_ego = 0.0

    self._v_offset = 0.0
    self._speed_limit = 0.0
    self._state = TurnSpeedControlState.inactive

    self._v_adapting = 0.0
    self._adapting_cycles = 0
    self._adapting_time = 0.

    self.v_turn_limit = 0.0
    self.a_turn_limit = 0.0
    self.v_turn_limit_future = 0.0

  @property
  def state(self):
    return self._state

  @state.setter
  def state(self, value):
    if value != self._state:
      _debug(f'Turn Speed Controller state: {_description_for_state(value)}')

      if value == TurnSpeedControlState.adapting:
        self._adapting_cycles = 0  # Reset adapting state cycle count when entereing state.
        # Adapting time must be  calculated at the moment we enter adapting state.
        self._adapting_time = abs(_LIMIT_ADAPT_TIME_PER_MS * self._v_offset)

    self._state = value

  @property
  def is_active(self):
    return self.state > TurnSpeedControlState.tempInactive

  @property
  def speed_limit(self):
    return self._speed_limit

  def _get_limit_from_map_data(self, sm):
    # Ignore if no live map data
    sock = 'liveMapData'
    if sm.logMonoTime[sock] is None:
      _debug('TS: No map data for speed limit')
      return 0.

    # Load limits from map_data
    map_data = sm[sock]
    speed_limit = 0.

    # Calculate the age of the gps fix. Ignore if too old.
    gps_fix_age = time.time() - map_data.lastGpsTimestamp * 1e-3
    if gps_fix_age > _MAX_MAP_DATA_AGE:
      _debug(f'TS: Ignoring map data as is too old. Age: {gps_fix_age}')
      return 0.

    # Ensure current speed limit is considered only if we are inside the section.
    if map_data.turnSpeedLimitValid and self._v_ego > 0.:
      speed_limit_end_time = (map_data.turnSpeedLimitEndDistance / self._v_ego) - gps_fix_age
      if speed_limit_end_time > 0.:
        speed_limit = map_data.turnSpeedLimit

    # Estimate the time left to reach new turn speed ahead (if any) and use it if we are close
    # enough while traveling when the turn speed is being reduced or set from 0.
    if map_data.turnSpeedLimitAheadValid and self._v_adapting > 0:
      next_speed_limit = map_data.turnSpeedLimitAhead
      if self._speed_limit == 0 or next_speed_limit <= self._speed_limit:
        next_speed_limit_time = (map_data.turnSpeedLimitAheadDistance / self._v_adapting) - gps_fix_age
        if next_speed_limit_time <= max(_LIMIT_ADAPT_TIME_PER_MS * (self._v_adapting - next_speed_limit),
                                        _MIN_LIMIT_ADAPT_TIME):
          speed_limit = next_speed_limit

    return speed_limit

  def _update_params(self):
    time = sec_since_boot()
    if time > self._last_params_update + 5.0:
      self._is_enabled = self._params.get("TurnSpeedControl", encoding='utf8') == "1"
      self._last_params_update = time

  def _update_calculations(self):
    # Update current velocity offset (error)
    self._v_offset = self._speed_limit - self._v_ego

  def _state_transition(self):
    # In any case, if op is disabled, or speed limit control is disabled
    # or the reported speed limit is 0, deactivate.
    if not self._op_enabled or not self._is_enabled or self._speed_limit == 0.:
      self.state = TurnSpeedControlState.inactive
      return

    # inactive
    if self.state == TurnSpeedControlState.inactive:
      # If the limit speed offset is negative (i.e. reduce speed) and lower than threshold
      # we go to adapting state to quickly reduce speed, otherwise we go directly to active
      if self._v_offset < _SPEED_OFFSET_TH:
        self.state = TurnSpeedControlState.adapting
      else:
        self.state = TurnSpeedControlState.active
    # adapting
    elif self.state == TurnSpeedControlState.adapting:
      self._adapting_cycles += 1
      # Go to active once the speed offset is over threshold.
      if self._v_offset >= _SPEED_OFFSET_TH:
        self.state = TurnSpeedControlState.active
    # active
    elif self.state == TurnSpeedControlState.active:
      # Go to adapting if the speed offset goes below threshold.
      if self._v_offset < _SPEED_OFFSET_TH:
        self.state = TurnSpeedControlState.adapting

  def _update_solution(self):
    # inactive
    if self.state == TurnSpeedControlState.inactive:
      # Preserve values
      self.v_turn_limit = self._v_ego
      self.a_turn_limit = self._a_ego
      self.v_turn_limit_future = self._v_ego
    # adapting
    elif self.state == TurnSpeedControlState.adapting:
      # Calculate to adapt speed on target time.
      adapting_time = max(self._adapting_time - self._adapting_cycles * _LON_MPC_STEP, 1.0)  # min adapt time 1 sec.
      a_target = (self._speed_limit - self._v_ego) / adapting_time
      # smooth out acceleration using jerk limits.
      j_limits = np.array(self._adapting_jerk_limits)
      a_limits = self._a_ego + j_limits * _LON_MPC_STEP
      a_target = max(min(a_target, a_limits[1]), a_limits[0])
      # calculate the solution values
      self.a_turn_limit = max(a_target, _MIN_ADAPTING_BRAKE_ACC)  # acceleration in next Longitudinal control step.
      self.v_turn_limit = self._v_ego + self.a_turn_limit * _LON_MPC_STEP  # speed in next Longitudinal control step.
      self.v_turn_limit_future = max(self._v_ego + self.a_turn_limit * 4., self._speed_limit)  # speed in 4 seconds.
    # active
    elif self.state == TurnSpeedControlState.active:
      # Calculate following same cruise logic in planner.py
      self.v_turn_limit, self.a_turn_limit = \
          speed_smoother(self._v_ego, self._a_ego, self._speed_limit, self._active_accel_limits[1],
                         self._active_accel_limits[0], self._active_jerk_limits[1], self._active_jerk_limits[0],
                         _LON_MPC_STEP)
      self.v_turn_limit = max(self.v_turn_limit, 0.)
      self.v_turn_limit_future = self._speed_limit

  def update(self, enabled, v_ego, a_ego, sm, accel_limits, jerk_limits):
    self._op_enabled = enabled
    self._v_ego = v_ego
    self._a_ego = a_ego
    self._active_accel_limits = accel_limits
    self._active_jerk_limits = jerk_limits

    # velocity before adapting should folow v_ego while not in adapting state.
    if self.state != TurnSpeedControlState.adapting:
      self._v_adapting = self._v_ego

    # Get the speed limit from Map Data
    self._speed_limit = self._get_limit_from_map_data(sm)

    self._update_params()
    self._update_calculations()
    self._state_transition()
    self._update_solution()

  def deactivate(self):
    self.state = TurnSpeedControlState.inactive
