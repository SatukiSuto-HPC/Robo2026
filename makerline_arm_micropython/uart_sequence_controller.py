# =============================================================================
# uart_sequence_controller.py - UART '1' 受信回数に応じた段階的動作シーケンス制御
# =============================================================================

import time
from machine import Pin, UART
import config

class SequenceState:
    IDLE = 0                    # 待機中（最初の1待ち、または終了）
    FORWARD_1 = 1               # 1回目 '1' 受信: 全センサ検知まで前進
    WAIT_FOR_SECOND_1 = 2       # 1回目前進完了後: 2回目 '1' 待ち
    TURN_RIGHT_1 = 3            # 2回目 '1' 受信: 右超信地旋回 (次の '1' まで)
    WAIT_FOR_THIRD_1 = 4        # 右旋回1完了後: 3回目 '1' 待ち
    FORWARD_2 = 5               # 3回目 '1' 受信: 全センサ検知まで前進
    WAIT_FOR_FOURTH_1 = 6       # 2回目前進完了後: 4回目 '1' 待ち
    TURN_RIGHT_2 = 7            # 4回目 '1' 受信: 右超信地旋回 (次の '1' まで)
    WAIT_FOR_FIFTH_1 = 8        # 右旋回2完了後: 5回目 '1' 待ち
    TURN_LEFT_AND_TRACK = 9     # 5回目 '1' 受信: 左旋回してからライントレース開始
    WAIT_FOR_FINAL_1 = 10       # トレース中: 最後の '1' 待ち
    STOPPED = 11                # 停止中

class UARTSequenceController:
    def __init__(self, line_follower):
        self._line_follower = line_follower
        self._state = SequenceState.IDLE
        self._recv_count = 0
        
        # 内部処理用の状態タイマーやフラグ
        self._turn_start_time = 0
        self._left_turn_phase = 0  # 0: 左旋回中(ライン脱出/探索), 1: ライン再検知後トレース移行
        
        # UARTの初期化 (line_follower と同様のポート設定)
        self._uart = None
        if hasattr(config, 'RPI_UART_TX_PIN') and hasattr(config, 'RPI_UART_RX_PIN'):
            try:
                self._uart = UART(
                    config.RPI_UART_ID,
                    baudrate=config.RPI_UART_BAUDRATE,
                    tx=Pin(config.RPI_UART_TX_PIN),
                    rx=Pin(config.RPI_UART_RX_PIN)
                )
                print("[UART SEQ] UART initialized successfully.")
            except Exception as e:
                print(f"[UART SEQ ERROR] {e}")

    def begin(self):
        self._state = SequenceState.IDLE
        self._recv_count = 0
        print("[UART SEQ] Controller initialized. Waiting for activation or UART '1'.")

    def start(self):
        # 外部（Webサーバーなど）からシーケンスを開始させる場合
        self._state = SequenceState.IDLE
        self._recv_count = 0
        print("[UART SEQ] Sequence controller ready. Listening for '1'.")

    def stop(self):
        self._state = SequenceState.STOPPED
        self._line_follower.stop()
        print("[UART SEQ] Sequence stopped.")

    def get_state(self):
        return self._state

    def get_recv_count(self):
        return self._recv_count

    def update(self):
        # 1. UARTからのデータ読み取りと受信回数のカウント
        if self._uart and self._uart.any():
            try:
                data = self._uart.read()
                if data:
                    for b in data:
                        char = chr(b)
                        if char == '1':
                            self._recv_count += 1
                            print(f"[UART SEQ] Received '1' (# {self._recv_count}), Current State: {self._state}")
                            self.handle_uart_trigger(self._recv_count)
                        elif char == '0':
                            print("[UART SEQ] Received '0' -> Stopping.")
                            self.stop()
            except Exception as e:
                print(f"[UART SEQ READ ERROR] {e}")

        # 2. ステートに応じた動作処理
        if self._state == SequenceState.FORWARD_1:
            # 全センサ検知 (0x0F または 15) まで前進
            self._line_follower.read_sensors()
            pattern = self._line_follower.get_sensor_pattern()
            
            if pattern == 0x0F:
                print("[UART SEQ] Forward 1: All sensors detected (cross/marker). Stopping and waiting for 2nd '1'.")
                self._line_follower.stop()
                self._state = SequenceState.WAIT_FOR_SECOND_1
            else:
                self.execute_forward_step()

        elif self._state == SequenceState.TURN_RIGHT_1:
            # 右方向に超信地旋回 (次の '1' が来るまで継続。UART受信側で state が変わる)
            self.execute_pivot_right_step()

        elif self._state == SequenceState.FORWARD_2:
            # 全センサ検知 (0x0F) まで前進
            self._line_follower.read_sensors()
            pattern = self._line_follower.get_sensor_pattern()
            
            if pattern == 0x0F:
                print("[UART SEQ] Forward 2: All sensors detected. Stopping and waiting for 4th '1'.")
                self._line_follower.stop()
                self._state = SequenceState.WAIT_FOR_FOURTH_1
            else:
                self.execute_forward_step()

        elif self._state == SequenceState.TURN_RIGHT_2:
            # 右方向に超信地旋回 (次の '1' が来るまで継続)
            self.execute_pivot_right_step()

        elif self._state == SequenceState.TURN_LEFT_AND_TRACK:
            # 5回目の '1' 受信後: 左旋回をしたのちに検知した線をトレースする
            self._line_follower.read_sensors()
            pattern = self._line_follower.get_sensor_pattern()
            
            if self._left_turn_phase == 0:
                # まず左超信地旋回を実行し、一度ラインから外れるか、あるいはラインを再検知するまで回る
                # ここでは「左超信地旋回を実行し、ラインを検出したらトレースに移行」とする
                now = time.ticks_ms()
                elapsed = time.ticks_diff(now, self._turn_start_time)
                
                # 最低旋回時間を確保してからセンサ検知を有効にする
                if elapsed >= 200 and pattern != 0:
                    print("[LINE] Line detected after left turn. Starting line tracking.")
                    self._left_turn_phase = 1
                    self._line_follower.start_tracking()
                else:
                    self.execute_pivot_left_step()
            elif self._left_turn_phase == 1:
                # 通常のライントレースを実行
                self._line_follower.update()
                # トレース中に最後の '1' が受信されると handle_uart_trigger で STOPPED に移行する

    def handle_uart_trigger(self, count):
        """
        UARTで '1' を受信した回数に応じた状態遷移の制御
        """
        if count == 1 and self._state == SequenceState.IDLE:
            print("[UART SEQ] -> State: FORWARD_1 (Moving forward until all sensors detected)")
            self._state = SequenceState.FORWARD_1

        elif count == 2 and self._state == SequenceState.WAIT_FOR_SECOND_1:
            print("[UART SEQ] -> State: TURN_RIGHT_1 (Pivoting right until next '1')")
            self._state = SequenceState.TURN_RIGHT_1

        elif count == 3 and self._state == SequenceState.TURN_RIGHT_1:
            print("[UART SEQ] -> State: FORWARD_2 (Moving forward until all sensors detected)")
            self._state = SequenceState.FORWARD_2

        elif count == 4 and self._state == SequenceState.WAIT_FOR_FOURTH_1:
            print("[UART SEQ] -> State: TURN_RIGHT_2 (Pivoting right until next '1')")
            self._state = SequenceState.TURN_RIGHT_2

        elif count == 5 and self._state == SequenceState.TURN_RIGHT_2:
            print("[UART SEQ] -> State: TURN_LEFT_AND_TRACK (Pivoting left then tracking line)")
            self._state = SequenceState.TURN_LEFT_AND_TRACK
            self._left_turn_phase = 0
            self._turn_start_time = time.ticks_ms()

        elif count >= 6 and self._state == SequenceState.TURN_LEFT_AND_TRACK:
            print("[UART SEQ] -> State: STOPPED (Final '1' received. Stopping cart.)")
            self.stop()

    def execute_forward_step(self):
        # 左右両モータを前進させるパルス出力
        invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
        fwd_val = 0 if invert else 1
        
        self._line_follower._left_dir.value(fwd_val)
        self._line_follower._right_dir.value(fwd_val)
        
        # ステップパルス生成 (base step delay を利用)
        self._line_follower._left_step.value(1)
        time.sleep_us(5)
        self._line_follower._left_step.value(0)
        time.sleep_us(5)
        self._line_follower._right_step.value(1)
        time.sleep_us(10)
        self._line_follower._right_step.value(0)
        time.sleep_us(config.BASE_STEP_DELAY)

    def execute_pivot_right_step(self):
        # 右方向への超信地旋回 (左輪前進、右輪後進)
        invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
        left_fwd = 0 if invert else 1
        right_rev = 1 if invert else 0
        
        self._line_follower._left_dir.value(left_fwd)
        self._line_follower._right_dir.value(right_rev)
        
        self._line_follower._left_step.value(1)
        time.sleep_us(5)
        self._line_follower._left_step.value(0)
        time.sleep_us(5)
        self._line_follower._right_step.value(1)
        time.sleep_us(10)
        self._line_follower._right_step.value(0)
        time.sleep_us(config.TURN_STEP_DELAY)

    def execute_pivot_left_step(self):
        # 左方向への超信地旋回 (左輪後進、右輪前進)
        invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
        left_rev = 1 if invert else 0
        right_fwd = 0 if invert else 1
        
        self._line_follower._left_dir.value(left_rev)
        self._line_follower._right_dir.value(right_fwd)
        
        self._line_follower._left_step.value(1)
        time.sleep_us(5)
        self._line_follower._left_step.value(0)
        time.sleep_us(5)
        self._line_follower._right_step.value(1)
        time.sleep_us(10)
        self._line_follower._right_step.value(0)
        time.sleep_us(config.TURN_STEP_DELAY)
