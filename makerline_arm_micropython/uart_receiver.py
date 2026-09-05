# =============================================================================
# uart_receiver.py - Raspberry Pi/QR UART event receiver (改訂版)
# =============================================================================
# 【変更点】
# - バイト単位受信 → 改行区切りのライン単位受信に変更
# - QRコードの内容文字列を保持する _pending_qr_list を導入
# - consume_trigger(qr_data=None) に qr_data 引数を追加
#   - None  : 任意のトリガーを消費
#   - ""    : 内容不問のQR（旧 '1' と等価）
#   - "xxx" : 内容が "xxx" と一致するQRだけ消費
# - qrcode_uart.py から QRデータ文字列をそのまま送信してもらう前提
#   （例: "pickup_zone\n" を受信 → _pending_qr_list に "pickup_zone" を追加）
# - 旧プロトコル '1\n' も互換として "任意QR" として処理
# =============================================================================

from machine import Pin, UART
import config


class UartEventReceiver:
    """UART2 を所有し、ライン単位でQRトリガーイベントを管理するクラス。"""

    def __init__(self):
        self._uart = None
        self._line_buf = b""          # 改行待ちバッファ
        self._pending_qr_list = []    # 受信したQRデータ文字列のキュー
        self._stop_requested = False
        try:
            self._uart = UART(
                config.RPI_UART_ID,
                baudrate=config.RPI_UART_BAUDRATE,
                tx=Pin(config.RPI_UART_TX_PIN),
                rx=Pin(config.RPI_UART_RX_PIN),
            )
            print("[UART RX] UART initialized successfully.")
        except Exception as e:
            print(f"[UART RX ERROR] {e}")

    def update(self):
        """メインループから毎回呼ぶ。受信データをライン単位で処理する。"""
        if not self._uart or not self._uart.any():
            return
        try:
            data = self._uart.read()
            if not data:
                return
            self._line_buf += data
            # バッファ内の完成行をすべて処理
            while b"\n" in self._line_buf:
                idx = self._line_buf.index(b"\n")
                line = self._line_buf[:idx].decode('utf-8', 'ignore').strip()
                self._line_buf = self._line_buf[idx + 1:]
                if line:
                    self._process_line(line)
        except Exception as e:
            print(f"[UART RX READ ERROR] {e}")

    def _process_line(self, line: str):
        """受信した1行を解析してイベントキューに積む。"""
        upper = line.upper()

        if upper == "0":
            # 停止コマンド
            self._stop_requested = True
            print("[UART RX] Stop requested.")

        elif "PING" in upper:
            # 自動検出用PINGに応答
            if self._uart:
                self._uart.write(b"ESP32_MAKERLINE_ARM_ACK\n")
            print("[UART RX] PING received, ACK sent.")

        elif upper == "1":
            # 旧プロトコル互換: '1' は「内容不問のQRトリガー」として扱う
            self._pending_qr_list.append("")
            print(f"[UART RX] Legacy trigger '1' received (pending: {len(self._pending_qr_list)})")

        else:
            # QRコード内容文字列（例: "pickup_zone"）
            self._pending_qr_list.append(line)
            print(f"[UART RX] QR data received: '{line}' (pending: {len(self._pending_qr_list)})")

    def consume_trigger(self, qr_data=None) -> bool:
        """
        トリガーイベントを1つ消費して True を返す。

        qr_data=None  : 内容問わず最初のトリガーを消費
        qr_data=""    : 内容不問のトリガー（旧 '1' 含む）を消費
        qr_data="xxx" : 内容が "xxx" と完全一致するトリガーだけ消費
        """
        if not self._pending_qr_list:
            return False

        if qr_data is None:
            # 任意消費
            self._pending_qr_list.pop(0)
            return True

        # 完全一致を先に探す
        for i, item in enumerate(self._pending_qr_list):
            if item == qr_data:
                self._pending_qr_list.pop(i)
                return True

        # qr_data="" なら最初のものを消費（内容不問）
        if qr_data == "" and self._pending_qr_list:
            self._pending_qr_list.pop(0)
            return True

        return False

    def consume_stop(self) -> bool:
        """停止イベントを1度だけ消費して True を返す。"""
        if not self._stop_requested:
            return False
        self._stop_requested = False
        return True

    def has_pending_trigger(self) -> bool:
        """未処理のトリガーが1件以上あれば True。"""
        return len(self._pending_qr_list) > 0

    def pending_count(self) -> int:
        """未処理トリガーの件数を返す。"""
        return len(self._pending_qr_list)
