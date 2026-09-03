# =============================================================================
# config.py - Config.h と連動する一括設定ファイル
# =============================================================================

# --- ハードウェアピン設定 (ESP32) ---

# 4個のデジタルラインセンサのピン (S3 〜 S0)
SENSOR_PIN_S3 = 32  # 左外側
SENSOR_PIN_S2 = 33  # 左内側
SENSOR_PIN_S1 = 34  # 右内側
SENSOR_PIN_S0 = 35  # 右外側

# DRV8825 ステッピングモータドライバのピン
LEFT_STEP_PIN = 19
LEFT_DIR_PIN = 18
RIGHT_STEP_PIN = 17
RIGHT_DIR_PIN = 16

# モータの回転方向の反転 (車体の前後向きやモータ配線が逆の場合は True)
INVERT_MOTOR_DIRECTION = True

# 2軸ロボットアーム (Arduino Uno 経由で制御するため、直接の PWM ピン割り当ては不要)
# SERVO_PIN_JOINT1 = 25  # Arduino に移行
# SERVO_PIN_JOINT2 = 26  # Arduino に移行

# Raspberry Pi UART通信 (QRコード連携)
RPI_UART_ID = 2
RPI_UART_RX_PIN = 21
RPI_UART_TX_PIN = 22
RPI_UART_BAUDRATE = 9600

# Arduino Uno UART通信 (アーム制御)
UNO_UART_ID = 1
UNO_UART_RX_PIN = 4
UNO_UART_TX_PIN = 5
UNO_UART_BAUDRATE = 9600


# --- ライントレースのパラメータ ---
BASE_STEP_DELAY = 1200  # 基本ステップ間隔 (マイクロ秒)
MIN_STEP_DELAY = 400    # [変更] 600 -> 400 (カーブ外輪の最高速度アップ)
MAX_STEP_DELAY = 4000   # [変更] 2500 -> 4000 (カーブ内輪の最低速度ダウン)

LINE_KP = 250.0         # [変更] 150.0 -> 250.0 (旋回の反応をアグレッシブに)

# 全センサ検知パターン (0x0F = 2進数 1111: 全センサがライン/マーカー上)
ALL_LINE_DETECT_PATTERN = 0x0F
ALL_LINE_DEBOUNCE_MS = 80

AUTO_RESUME_TRACKING_AFTER_TEACH = True
LINE_PASS_DURATION_MS = 600

TURN_STEP_DELAY = 1200
ARC_TURN_INNER_DELAY = 4000   # 緩旋回(アークターン)時の内輪ディレイ (値が大きい = 内輪が遅い = より急な旋回)
MIN_TURN_DURATION_MS = 200
MAX_TURN_DURATION_MS = 5000   # [修正] 安全タイムアウト: ラインが見つからない場合、5秒後に旋回を停止


# --- 通信設定 ---
SERIAL_BAUDRATE = 9600
