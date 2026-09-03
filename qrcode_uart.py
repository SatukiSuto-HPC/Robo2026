import cv2
import serial
import serial.tools.list_ports
import time
from pyzbar.pyzbar import decode

# UART設定
BAUD_RATE = 9600
ACK_STRING = "ESP32_MAKERLINE_ARM_ACK"
RETRY_INTERVAL = 5.0  # 自動検出を再試行する間隔 (秒)

def find_esp32_port():
    """利用可能なシリアルポートをスキャンし、ESP32を自動検出する"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        port_name = port.device
        try:
            with serial.Serial(port_name, baudrate=BAUD_RATE, timeout=0.8) as ser:
                time.sleep(0.3)
                ser.reset_input_buffer()
                
                # PING送信
                ser.write(b"PING\n")
                time.sleep(0.2)
                
                # 応答確認
                lines = ser.readlines()
                for line in lines:
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    if ACK_STRING in decoded:
                        print(f"[SUCCESS] ESP32 automatically detected on {port_name} @ {BAUD_RATE} baud!")
                        return port_name
        except (OSError, serial.SerialException):
            continue
            
    return None

def main():
    ser = None
    last_retry_time = 0.0

    # 1. USBカメラのオープン (通常は 0)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open USB camera.")
        return

    print("Starting QR code detector with ESP32 auto-detection & periodic retry. Press 'q' to exit.")
    
    qr_detected_prev = False

    try:
        while True:
            current_time = time.time()

            # シリアル未接続の場合、一定周期(RETRY_INTERVAL)で自動検出をリトライ
            if ser is None or not ser.is_open:
                if current_time - last_retry_time >= RETRY_INTERVAL:
                    last_retry_time = current_time
                    print("[INFO] Searching for ESP32...")
                    detected_port = find_esp32_port()
                    if detected_port:
                        try:
                            ser = serial.Serial(detected_port, BAUD_RATE, timeout=1)
                            print(f"[CONNECT] Connected to ESP32 on {detected_port}")
                        except Exception as e:
                            print(f"[ERR] Failed to open port {detected_port}: {e}")
                            ser = None
                    else:
                        print("[INFO] ESP32 not found. Retrying in 5 seconds...")

            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to grab frame.")
                break

            # pyzbarによるQRコード検出
            decoded_objects = decode(frame)
            current_detected = len(decoded_objects) > 0

            if current_detected:
                # 新しくQRコードを検出した瞬間
                if not qr_detected_prev:
                    print("QR Code detected!")
                    for obj in decoded_objects:
                        qr_data = obj.data.decode('utf-8')
                        print(f"Data: {qr_data}")

                    # UARTで '1' を送信 (左旋回トリガー)
                    if ser and ser.is_open:
                        try:
                            ser.write(b'1')
                            print("Sent '1' via UART (Trigger Left Turn).")
                        except Exception as e:
                            print(f"[ERR] Lost connection during write: {e}")
                            ser.close()
                            ser = None
                    else:
                        print("[WARN] QR detected, but ESP32 is not connected (UART disabled).")

                qr_detected_prev = True
            else:
                qr_detected_prev = False

            # デバッグ用に映像を表示
            for obj in decoded_objects:
                points = obj.polygon
                if len(points) > 4:
                    hull = cv2.convexHull(
                        cv2.array([(p.x, p.y) for p in points], dtype=cv2.float32)
                    )
                    points = hull
                
                n = len(points)
                for j in range(n):
                    pt1 = (points[j][0], points[j][1])
                    pt2 = (points[(j + 1) % n][0], points[(j + 1) % n][1])
                    cv2.line(frame, pt1, pt2, (0, 255, 0), 3)

            cv2.imshow("QR Code Reader (Auto-Retry)", frame)

            # 'q'キーで終了
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        if ser and ser.is_open:
            ser.close()
            print("Serial port closed.")

if __name__ == '__main__':
    main()
