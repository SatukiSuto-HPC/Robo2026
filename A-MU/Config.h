#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// =============================================================================
// 近藤科学 (KONDO) KRS-786ICS サーボモータ設定 (上下 + 開閉の2軸角度制御)
// =============================================================================

// USBシリアル通信ボーレート
constexpr unsigned long SERIAL_BAUD_RATE = 115200;

// 外部GPIOシリアル通信設定 (SoftwareSerial: D5=RX, D6=TX)
namespace GpioSerialConfig {
    constexpr int PIN_RX = 5;                  // 受信ピン (Arduino RX <- 外部機器TX)
    constexpr int PIN_TX = 6;                  // 送信ピン (Arduino TX -> 外部機器RX)
    constexpr unsigned long BAUD_RATE = 9600;  // 通信ボーレート (9600 bps)
}

// KRS-786ICS サーボモータ仕様 (PWM制御モード)
namespace KRS786Spec {
    constexpr int MIN_PULSE_US     = 700;   // 0度 パルス幅 (近藤科学標準 700〜750us)
    constexpr int NEUTRAL_PULSE_US = 1500;  // 90度 (中央) パルス幅
    constexpr int MAX_PULSE_US     = 2300;  // 180度 パルス幅 (近藤科学標準 2250〜2300us)
}

// アーム設定 (上下 + 開閉)
namespace ArmConfig {
    // 信号ピン (PWMピン)
    constexpr int PIN_ELEVATION = 9;   // 上下動作用サーボピン (Servo 1)
    constexpr int PIN_GRIPPER   = 10;  // 開閉用サーボピン (Servo 2)

    // 起動時の挙動設定
    // false: コマンドを受信するまでPWMパルスを出力せず脱力（起動時の勝手な回転を防止）
    // true: 起動直後に初期角度へ即座に通電移動
    constexpr bool ATTACH_ON_STARTUP = false;

    // 上下方向 (Elevation) 可動範囲・初期角度 (度)
    constexpr int MIN_ELEVATION_ANGLE  = 0;
    constexpr int MAX_ELEVATION_ANGLE  = 180;
    constexpr int INIT_ELEVATION_ANGLE = 90;

    // 開閉 (Gripper) 可動範囲・初期角度 (度)
    constexpr int MIN_GRIPPER_ANGLE  = 0;
    constexpr int MAX_GRIPPER_ANGLE  = 180;
    constexpr int INIT_GRIPPER_ANGLE = 90;

    // 開閉ショートカット角度 (度)
    constexpr int OPEN_ANGLE  = 30;
    constexpr int CLOSE_ANGLE = 120;

    // デフォルト移動速度 (度/秒) ※0で最高速即時移動
    constexpr float DEFAULT_SPEED = 60.0f;
}

#endif // CONFIG_H
