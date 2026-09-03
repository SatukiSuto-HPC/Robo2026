# Handover: MakerLine Arm Integration (MicroPython & Arduino/PlatformIO)

This document provides a complete technical summary and handover guide for the **MakerLine + 2-Axis Robot Arm Integrated Controller** project for ESP32.

---

## 1. Project Overview

The project integrates a 4-sensor analog/digital line-following car (chassis driven by DRV8825 stepper motors) with a 2-axis robotic arm (driven by servos on GPIO 25 and 26). It supports:
- **Line Tracking & All-Line Trigger**: Automatic stopping and triggering of a taught arm sequence when all 4 sensors detect a marker line.
- **QR Code / External Command Integration**: Listening on UART2 (GPIO 21/22) for triggers (e.g. `'1'` from Raspberry Pi) to execute a left turn until the line is re-detected.
- **Teaching & Playback**: Recording arm waypoints and persisting them.
- **Web Control Dashboard**: Access Point (AP) mode web server allowing real-time telemetry monitoring, remote control commands (`START`, `STOP`, `HOME`, `REC`, `PLAY`), inverse kinematics (IK) coordinate moves, and parameter tuning.

---

## 2. Project Structure

Two versions/implementations are available in the workspace:

### A. MicroPython Version (Primary / Current Port)
Located in `makerline_arm_micropython/`:
- **`config.py`**: Centralized pin definitions, tuning parameters, link lengths.
- **`boot.py`**: Wi-Fi AP setup (`SSID: zeni`, open network, static IP `192.168.4.1`).
- **`kinematics.py`**: Forward (FK) and Inverse (IK) kinematics math (`Point2D`, `JointAngles`).
- **`arm.py`**: 2-axis servo control (PWM pins 25 & 26) with S-curve interpolation.
- **`teaching.py`**: Waypoint recording and flash persistence (`teaching.json`).
- **`line_follower.py`**: 4-sensor line tracking, P-control on stepper drivers (pins 16-19), all-line detection, and UART2 left-turn trigger.
- **`web_server.py`**: Socket-based HTTP server on port 80 serving a dark-themed control dashboard (`/`, `/api/status`, `/api/command`, `/api/param`).
- **`main.py`**: Cooperative multitasking event loop (`arm.update()`, `teaching.update()`, `line_follower.update()`).

### B. Arduino / C++ PlatformIO Version (Original)
Located in root (`makerline_arm_integration/`):
- **`platformio.ini`**: Configured with `espressif32@6.8.1` (Arduino core 2.0.17) and dependencies (`ESP32Servo`, `ESP Async WebServer`, `ArduinoJson`).
- **`makerline_arm_integration.ino`**: Main sketch.
- **`WebManager.{h,cpp}`**: Async Web Server and embedded HTML dashboard (optimized to serve from flash via `PROGMEM`).
- **`ArmController.{h,cpp}`, `Kinematics.{h,cpp}`, `LineFollower.{h,cpp}`, `TeachingManager.{h,cpp}`, `CommandParser.{h,cpp}`**: Core C++ modules.

---

## 3. Hardware Connections (ESP32-WROOM-32E)

| Component | Pin / Port | Detail |
|---|---|---|
| **MakerLine Sensors (4 Digital)** | S3: GPIO 32, S2: GPIO 33, S1: GPIO 34, S0: GPIO 35 | Line detection inputs |
| **DRV8825 Stepper Drivers** | M1 (Left): STEP=19, DIR=18<br>M2 (Right): STEP=17, DIR=16 | Chassis motion control |
| **2-Axis Robot Arm Servos** | Joint 1 (Base): GPIO 25<br>Joint 2 (Elbow): GPIO 26 | PWM servo control (50Hz) |
| **Raspberry Pi UART (UART2)** | RX2: GPIO 21, TX2: GPIO 22 | 9600 baud (receives `'1'` for left turn) |

---

## 4. How to Use / Run (MicroPython)

1. **Flash MicroPython Firmware** onto ESP32.
2. **Upload Files** to ESP32 root using `ampy` or `Thonny`:
   ```bash
   ampy --port COM15 put config.py config.py
   ampy --port COM15 put boot.py boot.py
   ampy --port COM15 put kinematics.py kinematics.py
   ampy --port COM15 put arm.py arm.py
   ampy --port COM15 put teaching.py teaching.py
   ampy --port COM15 put line_follower.py line_follower.py
   ampy --port COM15 put web_server.py web_server.py
   ampy --port COM15 put main.py main.py
   ```
3. **Connect to Wi-Fi**:
   - SSID: `zeni` (No password / Open Network)
   - Gateway IP: `192.168.4.1`
4. **Access Dashboard**:
   - Open browser and navigate to `http://192.168.4.1`.
