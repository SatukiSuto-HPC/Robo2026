# =============================================================================
# line_follower.py - 4-Sensor Line Tracking & Stepper Driver (DRV8825)
# =============================================================================

import time
from machine import Pin, UART
import config

class LineFollowerState:
    IDLE = 0
    TRACKING = 1
    TURN_LEFT = 2

class LineFollower:
    def __init__(self):
        self._state = LineFollowerState.IDLE
        self._sensor_pattern = 0
        self._sensor_error = 0
        self._base_step_delay = config.BASE_STEP_DELAY
        self._motor_trim = getattr(config, 'MOTOR_TRIM', 0)
        self._is_line_candidate = False
        self._line_detect_start_time = 0
        self._has_triggered_on_current_line = False
        self._turn_start_time = 0

        self._last_step_time_us = time.ticks_us()
        # [FIX] Independent per-motor step schedulers for differential P-control
        self._left_next_step_us = time.ticks_us()
        self._right_next_step_us = time.ticks_us()

        # Hardware Pins for Stepper Motors (DRV8825)
        self._left_step = Pin(config.LEFT_STEP_PIN, Pin.OUT)
        self._left_dir = Pin(config.LEFT_DIR_PIN, Pin.OUT)  # [FIX] direct ref (removed dead DIR_PIN check)
        self._right_step = Pin(config.RIGHT_STEP_PIN, Pin.OUT)
        self._right_dir = Pin(config.RIGHT_DIR_PIN, Pin.OUT)

        # Hardware Pins for Sensors
        self._sensor_s3 = Pin(config.SENSOR_PIN_S3, Pin.IN)
        self._sensor_s2 = Pin(config.SENSOR_PIN_S2, Pin.IN)
        self._sensor_s1 = Pin(config.SENSOR_PIN_S1, Pin.IN)
        self._sensor_s0 = Pin(config.SENSOR_PIN_S0, Pin.IN)

        # UART for Raspberry Pi commands (e.g., QR Code trigger)
        self._uart = None
        if hasattr(config, 'RPI_UART_TX_PIN') and hasattr(config, 'RPI_UART_RX_PIN'):
            try:
                from machine import UART
                self._uart = UART(config.RPI_UART_ID, baudrate=config.RPI_UART_BAUDRATE, tx=Pin(config.RPI_UART_TX_PIN), rx=Pin(config.RPI_UART_RX_PIN))
            except Exception as e:
                print(f"[UART ERROR] {e}")

    def begin(self):
        self.stop()
        try:
            self._left_step.value(0)
            self._right_step.value(0)
            self._left_dir.value(0)
            self._right_dir.value(0)
        except Exception:
            pass

    def update(self):
        # 1. Read UART for external commands
        if self._uart and self._uart.any():
            try:
                data = self._uart.read()
                if data:
                    for b in data:
                        if chr(b) == '1':
                            print("[UART] Received '1' -> Triggering Left Turn.")
                            self.start_turn_left()
                        elif chr(b) == '0':
                            print("[UART] Received '0' -> Stopping cart.")
                            self.stop()
            except Exception:
                pass

        # 2. State Machine Update
        if self._state == LineFollowerState.IDLE:
            return

        elif self._state == LineFollowerState.TRACKING:
            self.read_sensors()
            # [FIX] Removed automatic stop on cross marker. Only stop via Web/UART.
            self.execute_tracking_step()

        elif self._state == LineFollowerState.TURN_LEFT:
            # Continue turning until sensors find line again
            self.read_sensors()
            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, self._turn_start_time)

            if elapsed >= config.MIN_TURN_DURATION_MS and self._sensor_pattern != 0:
                print("[LINE] Turn left complete. Resuming tracking.")
                self._state = LineFollowerState.TRACKING
            else:
                self.execute_turn_left_step()

    def start_tracking(self):
        self._state = LineFollowerState.TRACKING
        self._has_triggered_on_current_line = False
        now_us = time.ticks_us()
        self._left_next_step_us = now_us
        self._right_next_step_us = now_us
        print("[LINE] Started line tracking.")

    def stop(self):
        self._state = LineFollowerState.IDLE
        print("[LINE] Stopped.")

    def start_turn_left(self):
        self._state = LineFollowerState.TURN_LEFT
        self._turn_start_time = time.ticks_ms()

    def read_sensors(self):
        # Read 4 digital sensors (S3, S2, S1, S0)
        # Assuming HIGH (1) = black line, LOW (0) = white background (or vice versa)
        s3 = 1 if self._sensor_s3.value() else 0
        s2 = 1 if self._sensor_s2.value() else 0
        s1 = 1 if self._sensor_s1.value() else 0
        s0 = 1 if self._sensor_s0.value() else 0

        self._sensor_pattern = (s3 << 3) | (s2 << 2) | (s1 << 1) | s0

        # Calculate P-control error based on sensor weights: [-3, -1, +1, +3]
        # S3, S2 (left side), S1, S0 (right side)
        weight = 0
        active_count = 0
        if s3:
            weight -= 3; active_count += 1
        if s2:
            weight -= 1; active_count += 1
        if s1:
            weight += 1; active_count += 1
        if s0:
            weight += 3; active_count += 1

        if active_count > 0:
            self._sensor_error = weight
        else:
            # Maintain previous error if lost briefly
            pass



    def execute_tracking_speed(self):
        # Compute differential delays for left and right motors using P-control + Trim
        correction = int(config.LINE_KP * self._sensor_error)
        left_delay  = self._base_step_delay - correction - self._motor_trim
        right_delay = self._base_step_delay + correction + self._motor_trim

        left_delay  = max(config.MIN_STEP_DELAY, min(config.MAX_STEP_DELAY, left_delay))
        right_delay = max(config.MIN_STEP_DELAY, min(config.MAX_STEP_DELAY, right_delay))

        left_forward = True
        right_forward = True

        # Arc turn (信地旋回) for sharp corners
        # Inner wheel slows down significantly while outer wheel drives forward
        inner_delay = getattr(config, 'ARC_TURN_INNER_DELAY', config.MAX_STEP_DELAY)
        if self._sensor_error <= -3:
            left_forward = True
            right_forward = True
            left_delay = inner_delay   # Inner wheel: very slow forward
            right_delay = config.TURN_STEP_DELAY  # Outer wheel: normal turn speed
        elif self._sensor_error >= 3:
            left_forward = True
            right_forward = True
            left_delay = config.TURN_STEP_DELAY  # Outer wheel: normal turn speed
            right_delay = inner_delay   # Inner wheel: very slow forward

        return left_delay, right_delay, left_forward, right_forward

    def execute_tracking_step(self):
        # Non-blocking differential P-control & Pivot turn
        left_delay, right_delay, left_fwd, right_fwd = self.execute_tracking_speed()
        now_us = time.ticks_us()

        step_left  = time.ticks_diff(now_us, self._left_next_step_us)  >= 0
        step_right = time.ticks_diff(now_us, self._right_next_step_us) >= 0

        if step_left or step_right:
            if step_left:
                self._left_next_step_us = time.ticks_add(self._left_next_step_us, left_delay)
                if time.ticks_diff(now_us, self._left_next_step_us) > left_delay:
                    self._left_next_step_us = now_us
            if step_right:
                self._right_next_step_us = time.ticks_add(self._right_next_step_us, right_delay)
                if time.ticks_diff(now_us, self._right_next_step_us) > right_delay:
                    self._right_next_step_us = now_us

            # Direction control
            invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
            fwd_val = 0 if invert else 1
            rev_val = 1 if invert else 0
            self._left_dir.value(fwd_val if left_fwd else rev_val)
            self._right_dir.value(fwd_val if right_fwd else rev_val)

            if step_left:
                self._left_step.value(1)
            time.sleep_us(5)
            if step_left:
                self._left_step.value(0)
            time.sleep_us(5)
            if step_right:
                self._right_step.value(1)
            time.sleep_us(10)
            if step_right:
                self._right_step.value(0)

    def execute_turn_left_step(self):
        # Arc turn: left wheel stopped, right wheel forward for gradual left turn
        invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
        fwd_val = 0 if invert else 1

        self._left_dir.value(fwd_val)
        self._right_dir.value(fwd_val)

        # Only pulse the right (outer) motor to arc forward-left
        self._right_step.value(1)
        time.sleep_us(10)
        self._right_step.value(0)
        time.sleep_us(config.TURN_STEP_DELAY)

    def step_motors(self, left_forward, right_forward):
        # [FIX] Corrected DIR polarity for counter-facing (back-to-back) motor layout:
        #   Forward = left HIGH, right LOW (they face opposite directions on the chassis)
        invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
        if invert:
            left_dir_val  = 0 if left_forward  else 1
            right_dir_val = 0 if right_forward else 1
        else:
            left_dir_val  = 1 if left_forward  else 0
            right_dir_val = 1 if right_forward else 0  # [FIX] Flipped to match execute_tracking_step

        self._left_dir.value(left_dir_val)
        self._right_dir.value(right_dir_val)

        # [FIX] Stagger left/right pulses to reduce simultaneous current spike (DRV8825 safety)
        self._left_step.value(1)
        time.sleep_us(5)
        self._left_step.value(0)
        time.sleep_us(5)
        self._right_step.value(1)
        time.sleep_us(10)
        self._right_step.value(0)

    def get_sensor_pattern(self):
        return self._sensor_pattern

    def get_sensor_error(self):
        return self._sensor_error

    def get_state(self):
        return self._state

    def set_base_delay(self, delay_us):
        self._base_step_delay = max(config.MIN_STEP_DELAY, min(config.MAX_STEP_DELAY, delay_us))

    def get_base_delay(self):
        return self._base_step_delay

    def set_motor_trim(self, trim):
        self._motor_trim = trim

    def get_motor_trim(self):
        return self._motor_trim
