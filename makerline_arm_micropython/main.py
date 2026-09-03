# =============================================================================
# main.py - Main Event Loop / Cooperative Multitasking for ESP32 MicroPython
# =============================================================================

import time
import sys
from line_follower import LineFollower
from web_server import WebServer
from uart_relay import UARTRelay

def main():
    print("[INIT] Starting MakerLine MicroPython Controller...")

    # 1. Initialize Modules
    line_follower = LineFollower()
    web_server = WebServer(line_follower)
    uart_relay = UARTRelay()

    # 2. Begin Hardware & Peripherals
    line_follower.begin()
    web_server.begin()
    uart_relay.begin()

    print("[MAIN LOOP] Entering cooperative multitasking loop...")

    # 5. Main Cooperative Loop
    while True:
        try:
            # Update Line Tracer & Sensor Monitoring
            line_follower.update()

            # Update Non-blocking Web Server requests
            web_server.update()
            
            # Update UART Relay (RPi -> Uno)
            uart_relay.update()

            # Small cooperative yield to prevent CPU starvation
            # [FIX] Run at max speed during tracking to ensure precise microsecond stepper timing
            if line_follower.get_state() == 0:  # IDLE
                time.sleep_ms(10)
            else:
                time.sleep_us(10)

        except KeyboardInterrupt:
            print("[MAIN] Interrupted by user. Stopping cart.")
            line_follower.stop()
            break
        except Exception as e:
            print(f"[MAIN ERROR] {e}")
            time.sleep(0.1)

if __name__ == '__main__':
    main()
