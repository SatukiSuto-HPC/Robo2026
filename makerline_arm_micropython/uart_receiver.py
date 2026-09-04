# =============================================================================
# uart_receiver.py - Raspberry Pi/QR UART event receiver
# =============================================================================

from machine import Pin, UART
import config


class UartEventReceiver:
    """Owns UART2 and exposes newline-independent trigger events."""

    def __init__(self):
        self._uart = None
        self._pending_triggers = 0
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
        if not self._uart or not self._uart.any():
            return

        try:
            data = self._uart.read()
            if not data:
                return
            for byte_value in data:
                char = chr(byte_value)
                if char == '1':
                    self._pending_triggers += 1
                    print(f"[UART RX] Trigger received (pending: {self._pending_triggers})")
                elif char == '0':
                    self._stop_requested = True
                    print("[UART RX] Stop requested.")
                elif char.upper() == 'P':
                    # Accept PING as a line-oriented probe without blocking on CR/LF.
                    self._send_ack_if_ping(data)
        except Exception as e:
            print(f"[UART RX READ ERROR] {e}")

    def _send_ack_if_ping(self, data):
        if b"PING" in data.upper():
            self._uart.write(b"ESP32_MAKERLINE_ARM_ACK\n")

    def consume_trigger(self):
        if self._pending_triggers <= 0:
            return False
        self._pending_triggers -= 1
        return True

    def consume_stop(self):
        if not self._stop_requested:
            return False
        self._stop_requested = False
        return True

    def has_pending_trigger(self):
        return self._pending_triggers > 0
