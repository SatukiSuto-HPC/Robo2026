# =============================================================================
# a-mu.py - Arduino Uno UART通信モジュール (ESP32 MicroPython用)
# =============================================================================
# 【概要】
# ESP32からArduino UnoへUART経由でアーム制御データを送信するモジュール。
# 初期状態では "0,175" を送信し、アームを初期位置に設定する。
# =============================================================================

from machine import UART, Pin
import time
import config


class ArmController:
    """Arduino Unoへアーム制御データをUART送信するクラス"""

    def __init__(self):
        # config.pyのUART設定を使用してArduino Uno用UARTを初期化
        self.uart = UART(
            config.UNO_UART_ID,
            baudrate=config.UNO_UART_BAUDRATE,
            tx=Pin(config.UNO_UART_TX_PIN),
            rx=Pin(config.UNO_UART_RX_PIN)
        )
        self._initialized = False

    def begin(self):
        """初期化処理: 初期データ "0,175" をArduinoへ送信する"""
        # Arduino側のブート完了を待つ
        time.sleep(1)
        self.send_data(0, 175)
        self._initialized = True
        print("[ARM] Initial position sent: 0,175")

    def send_data(self, joint1, joint2):
        """
        2つの角度値をカンマ区切り + 改行でArduinoへ送信する。

        Args:
            joint1: 関節1の角度値
            joint2: 関節2の角度値
        """
        message = f"{joint1},{joint2}\n"
        self.uart.write(message.encode())
        print(f"[ARM] Sent: {joint1},{joint2}")

    def update(self):
        """メインループから呼ばれる更新処理（将来の拡張用）"""
        # Arduino側からの応答を読み取る（あれば）
        if self.uart.any():
            response = self.uart.readline()
            if response:
                print(f"[ARM] Received: {response.decode().strip()}")
