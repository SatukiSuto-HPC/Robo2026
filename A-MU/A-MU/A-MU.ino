/**
 * @file A-MU.ino
 * @brief Arduino Uno R4 Minima アーム（上下＋開閉）シリアル制御メインプログラム (DS3218サーボ対応)
 */

#include <Arduino.h>
#include <Servo.h>
#include <SoftwareSerial.h>
#include "Config.h"
#include "Arm.h"
#include "CommandParser.h"

// アームインスタンスの生成
Arm arm(1);

// 外部GPIOシリアル (RX: Pin 5, TX: Pin 6)
SoftwareSerial gpioSerial(GpioSerialConfig::PIN_RX, GpioSerialConfig::PIN_TX);

// シリアルコマンドパーサーの生成 (USBシリアル用 & GPIOシリアル用)
CommandParser usbParser(arm, Serial);
CommandParser gpioParser(arm, gpioSerial);

void setup() {
    // USBシリアル通信の初期化 (115200 bps)
    Serial.begin(SERIAL_BAUD_RATE);

    // 外部GPIOシリアル通信の初期化 (9600 bps)
    gpioSerial.begin(GpioSerialConfig::BAUD_RATE);
    
    // UNO R4 MinimaのUSBシリアル接続待機 (最長1.5秒待機)
    unsigned long startWait = millis();
    while (!Serial && (millis() - startWait < 1500)) {
        delay(10);
    }

    Serial.println(F("\n=========================================="));
    Serial.println(F(" Arduino Uno R4 Arm Controller (KRS-786ICS)"));
    Serial.println(F(" Ports: USB Serial (115200) + GPIO D5/D6 (9600)"));
    Serial.println(F("=========================================="));

    gpioSerial.println(F("\n=========================================="));
    gpioSerial.println(F(" Arduino Uno R4 Arm Controller (KRS-786ICS)"));
    gpioSerial.println(F(" Ports: GPIO Serial (9600 bps: RX=D5, TX=D6)"));
    gpioSerial.println(F("=========================================="));

    // アームの初期化設定 (KRS-786ICS パルス幅 700〜2300us を適用)
    ArmJointConfig armElev = {
        ArmConfig::PIN_ELEVATION,
        ArmConfig::INIT_ELEVATION_ANGLE,
        ArmConfig::MIN_ELEVATION_ANGLE,
        ArmConfig::MAX_ELEVATION_ANGLE,
        ArmConfig::DEFAULT_SPEED,
        KRS786Spec::MIN_PULSE_US,
        KRS786Spec::MAX_PULSE_US,
        ArmConfig::ATTACH_ON_STARTUP
    };
    ArmJointConfig armGrip = {
        ArmConfig::PIN_GRIPPER,
        ArmConfig::INIT_GRIPPER_ANGLE,
        ArmConfig::MIN_GRIPPER_ANGLE,
        ArmConfig::MAX_GRIPPER_ANGLE,
        ArmConfig::DEFAULT_SPEED,
        KRS786Spec::MIN_PULSE_US,
        KRS786Spec::MAX_PULSE_US,
        ArmConfig::ATTACH_ON_STARTUP
    };
    arm.begin(armElev, armGrip, ArmConfig::OPEN_ANGLE, ArmConfig::CLOSE_ANGLE);

    Serial.println(F("Initialization complete. System ready."));
    gpioSerial.println(F("Initialization complete. System ready."));

    if (!ArmConfig::ATTACH_ON_STARTUP) {
        Serial.println(F("Note: Servos are FREE (standby). They will activate on your first command."));
        gpioSerial.println(F("Note: Servos are FREE (standby). They will activate on your first command."));
    }

    usbParser.printHelp();
    gpioParser.printHelp();
}

void loop() {
    // USBシリアルおよびGPIOシリアルからのコマンド受信と解析
    usbParser.update();
    gpioParser.update();

    // サーボ位置更新（ノンブロッキングスムーズ移動）
    arm.update();
}
