# =============================================================================
# a-mu.py - Arduino Uno (A-MU.ino) アーム制御モジュール (ESP32 MicroPython用)
# =============================================================================
# 【概要】
# 本モジュールは、Arduino Uno R4 Minima 上で動作するサーボ制御プログラム (A-MU.ino) と
# UART (シリアル通信) 経由でコマンドの送受信を行い、ロボットアーム（上下動・開閉の2軸）を
# ESP32 から制御するためのクラスライブラリです。
#
# 【ハードウェア配線 (config.py 設定)】
# - ESP32 TX (GPIO 5) -> Arduino Pin 5 (RX)
# - ESP32 RX (GPIO 4) <- Arduino Pin 6 (TX)
# - ESP32 GND         -- Arduino GND (※必ずGNDを共通接続してください)
# - 通信速度: 9600 bps
#
# 【対応コマンド (A-MU.ino)】
# - 上下制御 (Servo 1 / D9) : S1:<角度>, S1:+<相対>, S1:-<相対>, S1:<角度>:<速度>
# - 開閉制御 (Servo 2 / D10): S2:<角度>, S2:+<相対>, S2:-<相対>, OPEN, CLOSE
# - 2軸同時制御             : POS:<S1>:<S2>, <S1>,<S2>, REL:<S1増減>:<S2増減>
# - ゼロ点・トルク管理       : ZERO, ORIGIN, ATTACH, FREE, STATUS
# =============================================================================

import time
from machine import Pin, UART
import config


class ArmController:
    """
    Arduino Uno (A-MU.ino) と UART 通信を行い、2軸アームを制御するクラス
    """

    def __init__(self, uart_id=None, baudrate=None, tx_pin=None, rx_pin=None):
        """
        アーム制御クラスの初期化
        引数が省略された場合は config.py の設定値を自動参照します。
        """
        self._uart_id = uart_id if uart_id is not None else getattr(config, 'UNO_UART_ID', 1)
        self._baudrate = baudrate if baudrate is not None else getattr(config, 'UNO_UART_BAUDRATE', 9600)
        self._tx_pin_num = tx_pin if tx_pin is not None else getattr(config, 'UNO_UART_TX_PIN', 5)
        self._rx_pin_num = rx_pin if rx_pin is not None else getattr(config, 'UNO_UART_RX_PIN', 4)

        self._uart = None
        self._is_initialized = False
        self._last_response = ""
        self._rx_buffer = bytearray()

        # 推定現在角度 (マイコン側キャッシュ)
        self._current_elevation = 90
        self._current_gripper = 90
        self._is_attached = False

    def begin(self) -> bool:
        """
        UART 通信ポートの初期化と通信開始
        """
        try:
            self._uart = UART(
                self._uart_id,
                baudrate=self._baudrate,
                tx=Pin(self._tx_pin_num),
                rx=Pin(self._rx_pin_num),
                timeout=50,
                rxbuf=256
            )
            self._is_initialized = True
            print(f"[ARM] UART initialized (ID:{self._uart_id}, Baud:{self._baudrate}, TX:{self._tx_pin_num}, RX:{self._rx_pin_num})")

            # 接続確認のため少し待機してからバッファをクリア
            time.sleep_ms(100)
            self.clear_rx_buffer()
            return True
        except Exception as e:
            print(f"[ARM INIT ERROR] Failed to initialize UART: {e}")
            self._is_initialized = False
            return False

    def clear_rx_buffer(self):
        """
        UART 受信バッファに残っている未読データをクリア
        """
        if self._uart and self._uart.any():
            try:
                self._uart.read()
            except Exception:
                pass

    def send_command(self, cmd: str) -> bool:
        """
        Arduino へシリアルコマンド文字列を送信 (末尾に改行 '\\n' を自動付与)
        """
        if not self._uart:
            if not self.begin():
                print(f"[ARM ERROR] Cannot send command (UART not ready): {cmd}")
                return False

        try:
            formatted_cmd = cmd.strip() + "\n"
            self._uart.write(formatted_cmd.encode('utf-8'))
            return True
        except Exception as e:
            print(f"[ARM ERROR] Failed to send command '{cmd}': {e}")
            return False

    def read_line(self) -> str:
        """
        Arduino からのレスポンスを1行読み出す（ノンブロッキング）
        データがない場合は None を返します。
        """
        if not self._uart or not self._uart.any():
            return None

        try:
            line = self._uart.readline()
            if line:
                decoded = line.decode('utf-8').strip()
                if decoded:
                    self._last_response = decoded
                    return decoded
        except Exception:
            pass
        return None

    def update(self):
        """
        メイン協調ループ内で定期実行する更新メソッド
        Arduino から届いたメッセージ（OK, ERR, STATUS など）を読み出し、コンソールに出力・反映します。
        """
        while True:
            resp = self.read_line()
            if resp is None:
                break
            print(f"[ARM RECV] {resp}")

            # 状態文字列の簡易解析
            if "SERVOS ATTACHED" in resp:
                self._is_attached = True
            elif "SERVOS DETACHED" in resp:
                self._is_attached = False

    # =========================================================================
    # 単軸制御メソッド (上下動: S1 / 開閉: S2)
    # =========================================================================

    def set_elevation(self, angle: int, speed: float = None) -> bool:
        """
        上下サーボ (Servo 1 / D9) の角度を指定 (0 〜 180度)
        :param angle: 目標角度 (度)
        :param speed: 移動速度 (度/秒, 省略時は最高速即時移動)
        """
        angle = max(0, min(180, int(angle)))
        self._current_elevation = angle
        if speed is not None and speed > 0:
            return self.send_command(f"S1:{angle}:{speed}")
        else:
            return self.send_command(f"S1:{angle}")

    def move_elevation(self, delta: int, speed: float = None) -> bool:
        """
        上下サーボ (Servo 1 / D9) を現在位置から相対移動
        :param delta: 移動量 (+度 または -度)
        :param speed: 移動速度 (度/秒)
        """
        delta = int(delta)
        sign = "+" if delta >= 0 else ""
        if speed is not None and speed > 0:
            return self.send_command(f"S1:{sign}{delta}:{speed}")
        else:
            return self.send_command(f"S1:{sign}{delta}")

    def set_gripper(self, angle: int, speed: float = None) -> bool:
        """
        開閉サーボ (Servo 2 / D10) の角度を指定 (0 〜 180度)
        :param angle: 目標角度 (度)
        :param speed: 移動速度 (度/秒)
        """
        angle = max(0, min(180, int(angle)))
        self._current_gripper = angle
        if speed is not None and speed > 0:
            return self.send_command(f"S2:{angle}:{speed}")
        else:
            return self.send_command(f"S2:{angle}")

    def move_gripper(self, delta: int, speed: float = None) -> bool:
        """
        開閉サーボ (Servo 2 / D10) を現在位置から相対移動
        :param delta: 移動量 (+度 または -度)
        :param speed: 移動速度 (度/秒)
        """
        delta = int(delta)
        sign = "+" if delta >= 0 else ""
        if speed is not None and speed > 0:
            return self.send_command(f"S2:{sign}{delta}:{speed}")
        else:
            return self.send_command(f"S2:{sign}{delta}")

    def open(self) -> bool:
        """
        グリッパーを開く (Arduino側の規定角度: 30度)
        """
        return self.send_command("OPEN")

    def close(self) -> bool:
        """
        グリッパーを閉じる (Arduino側の規定角度: 120度)
        """
        return self.send_command("CLOSE")

    # =========================================================================
    # 2軸同時制御メソッド
    # =========================================================================

    def set_angles(self, s1_angle: int, s2_angle: int, speed: float = None) -> bool:
        """
        2つのサーボの目標角度を同時に設定
        :param s1_angle: 上下角度 (0〜180度)
        :param s2_angle: 開閉角度 (0〜180度)
        :param speed: 移動速度 (度/秒)
        """
        s1 = max(0, min(180, int(s1_angle)))
        s2 = max(0, min(180, int(s2_angle)))
        self._current_elevation = s1
        self._current_gripper = s2

        if speed is not None and speed > 0:
            return self.send_command(f"POS:{s1}:{s2}:{speed}")
        else:
            return self.send_command(f"POS:{s1}:{s2}")

    def move_relative(self, delta_s1: int, delta_s2: int, speed: float = None) -> bool:
        """
        2つのサーボを同時に相対移動
        :param delta_s1: 上下の移動量 (度)
        :param delta_s2: 開閉の移動量 (度)
        :param speed: 移動速度 (度/秒)
        """
        if speed is not None and speed > 0:
            return self.send_command(f"REL:{int(delta_s1)}:{int(delta_s2)}:{speed}")
        else:
            return self.send_command(f"REL:{int(delta_s1)}:{int(delta_s2)}")

    # =========================================================================
    # トルク・電源・ゼロ点制御
    # =========================================================================

    def attach(self) -> bool:
        """
        サーボに通電し、トルクをONにする
        """
        return self.send_command("ATTACH")

    def detach(self) -> bool:
        """
        サーボを脱力（フリー状態）にしてトルクをOFFにする (手動で動かせます)
        """
        return self.send_command("FREE")

    def free(self) -> bool:
        """
        detach() のエイリアス
        """
        return self.detach()

    def set_zero(self, target: str = "") -> bool:
        """
        現在位置を新しい基準「0度」としてキャリブレーション登録
        :param target: "" (両軸), "S1" (上下のみ), "S2" (開閉のみ)
        """
        if target.upper() == "S1" or target.upper() == "UP":
            return self.send_command("ZERO:S1")
        elif target.upper() == "S2" or target.upper() == "GRIP":
            return self.send_command("ZERO:S2")
        else:
            return self.send_command("ZERO")

    def reset_zero(self) -> bool:
        """
        ゼロ点オフセットをリセットし、サーボ本来の物理原点 (0〜180度) に戻す
        """
        return self.send_command("ORIGIN")

    def request_status(self) -> bool:
        """
        Arduino へステータス要求コマンドを送信
        """
        return self.send_command("STATUS")

    def get_last_response(self) -> str:
        """
        直近に受信したArduinoからのレスポンスを取得
        """
        return self._last_response

    def deinit(self):
        """
        UART通信リソースの解放
        """
        if self._uart:
            try:
                self._uart.deinit()
            except Exception:
                pass
            self._uart = None
            self._is_initialized = False


# クラス名のエイリアス (Arm としても呼び出し可能)
Arm = ArmController


# =============================================================================
# スクリプト単体実行時の簡易テスト・対話デモ
# =============================================================================
if __name__ == '__main__':
    print("=== Arduino Arm Controller Test ===")
    arm = ArmController()
    if not arm.begin():
        print("初期化に失敗しました。配線やピン番号を確認してください。")
    else:
        print("アームコントローラの初期化が完了しました。")
        print("コマンド例: arm.open(), arm.close(), arm.set_elevation(90), arm.detach()")
        # 起動テスト: トルクON -> 開閉テスト
        time.sleep_ms(500)
        arm.attach()
        time.sleep_ms(300)
        print("グリッパーを開きます (OPEN)...")
        arm.open()
        time.sleep_ms(1000)
        print("グリッパーを閉じます (CLOSE)...")
        arm.close()
        time.sleep_ms(1000)
        arm.update()
        print("テスト完了。")
