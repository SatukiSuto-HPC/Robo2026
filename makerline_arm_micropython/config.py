# =============================================================================
# config.py - Centralized Configuration matching Config.h
# =============================================================================

# --- Hardware Pin Configuration (ESP32) ---

# 4 Digital Line Sensor Pins (S3 to S0)
SENSOR_PIN_S3 = 32  # Left outer
SENSOR_PIN_S2 = 33  # Left inner
SENSOR_PIN_S1 = 34  # Right inner
SENSOR_PIN_S0 = 35  # Right outer

# DRV8825 Stepper Motor Driver Pins
LEFT_STEP_PIN = 19
LEFT_DIR_PIN = 18
RIGHT_STEP_PIN = 17
RIGHT_DIR_PIN = 16

# Invert motor rotation direction (True if chassis front/back or motor wiring is reversed)
INVERT_MOTOR_DIRECTION = True

# 2-Axis Robot Arm (Now controlled via Arduino Uno, no direct PWM pins)
# SERVO_PIN_JOINT1 = 25  # Moved to Arduino
# SERVO_PIN_JOINT2 = 26  # Moved to Arduino

# Raspberry Pi UART (QR Code Integration)
RPI_UART_ID = 2
RPI_UART_RX_PIN = 21
RPI_UART_TX_PIN = 22
RPI_UART_BAUDRATE = 9600

# Arduino Uno UART (Data Relay)
UNO_UART_ID = 1
UNO_UART_RX_PIN = 4
UNO_UART_TX_PIN = 5
UNO_UART_BAUDRATE = 9600


# --- Line Follower Parameters ---
BASE_STEP_DELAY = 1200  # Base step interval in microseconds
MIN_STEP_DELAY = 400    # [MODIFIED] 600 -> 400 (カーブ外輪の最高速度アップ)
MAX_STEP_DELAY = 4000   # [MODIFIED] 2500 -> 4000 (カーブ内輪の最低速度ダウン)

LINE_KP = 250.0         # [MODIFIED] 150.0 -> 250.0 (旋回の反応をアグレッシブに)

# All-sensor detect pattern (0x0F = 1111 binary: all sensors on line / marker)
ALL_LINE_DETECT_PATTERN = 0x0F
ALL_LINE_DEBOUNCE_MS = 80

AUTO_RESUME_TRACKING_AFTER_TEACH = True
LINE_PASS_DURATION_MS = 600

TURN_STEP_DELAY = 1200
MIN_TURN_DURATION_MS = 200
MAX_TURN_DURATION_MS = 5000   # [FIX] Safety timeout: stop turning after 5s if line not found


# --- Communication ---
SERIAL_BAUDRATE = 9600
