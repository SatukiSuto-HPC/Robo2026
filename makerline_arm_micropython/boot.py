# =============================================================================
# boot.py - Robust Wi-Fi AP Setup for ESP32 MicroPython
# =============================================================================

import network
import time
import gc

gc.collect()

print("================================================================")
print("  MakerLine + 2-Axis Robot Arm Integrated Controller (MicroPython)")
print("================================================================")
print("[BOOT] Initializing Wi-Fi Access Point 'zeni'...")

# Disable STA interface to avoid interference
sta = network.WLAN(network.STA_IF)
sta.active(False)

# Configure AP interface
ap = network.WLAN(network.AP_IF)
ap.active(False)
time.sleep(0.2)

# Configure SSID and WPA2-PSK network
# [FIX] Changed from authmode=0 (OPEN) to WPA2-PSK to prevent unauthorized access
# NOTE: Change "hogehoge" to your own password before deployment.
AP_PASSWORD = "hogehoge"
ap.config(essid="zeni", authmode=4, password=AP_PASSWORD)
ap.active(True)

# Set static IP configuration (Default ESP32 AP Gateway: 192.168.4.1)
try:
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
except Exception as e:
    print("[WIFI AP WARNING] ifconfig error:", e)

# Wait for AP activation
timeout = 10
while not ap.active() and timeout > 0:
    time.sleep(0.5)
    timeout -= 1

if ap.active():
    ip_info = ap.ifconfig()
    print("[WIFI AP] Status: ACTIVE")
    print("[WIFI AP] SSID     : zeni (WPA2-PSK)")
    print(f"[WIFI AP] IP Addr  : http://{ip_info[0]}")
    print(f"[WIFI AP] Netmask  : {ip_info[1]}")
else:
    print("[WIFI AP ERROR] Failed to activate Access Point!")

print("----------------------------------------------------------------")
print("[SYSTEM READY] Starting main application loop...")
print("================================================================")
