# =============================================================================
# uart_relay.py - Forwards UART data from Raspberry Pi to Arduino Uno
# =============================================================================

from machine import UART
import config

class UARTRelay:
    def __init__(self):
        self.uno_uart = None

    def begin(self):
        print("[UART RELAY] Initializing Uno UART...")
        try:
            # Initialize Arduino Uno UART
            self.uno_uart = UART(
                config.UNO_UART_ID,
                baudrate=config.UNO_UART_BAUDRATE,
                rx=config.UNO_UART_RX_PIN,
                tx=config.UNO_UART_TX_PIN
            )
            print(f"[UART RELAY] Uno UART (ID:{config.UNO_UART_ID}, RX:{config.UNO_UART_RX_PIN}, TX:{config.UNO_UART_TX_PIN}) initialized.")
            
            # Send initial state to Arduino Uno on startup
            initial_msg = "0,175\n"
            self.uno_uart.write(initial_msg.encode('utf-8'))
            print(f"[UART RELAY] Sent initial state to Uno: {initial_msg.strip()}")
            
        except Exception as e:
            print(f"[UART RELAY ERROR] Failed to init UARTs: {e}")

    def update(self):
        # Data forwarding from Raspberry Pi to Arduino Uno has been disabled.
        pass
