#ifndef ARM_H
#define ARM_H

#include <Arduino.h>
#include "ServoJoint.h"

struct ArmJointConfig {
    int pin;
    int initAngle;
    int minAngle;
    int maxAngle;
    float defaultSpeed;
    int minPulseUs; // KRS-786ICS標準: 700
    int maxPulseUs; // KRS-786ICS標準: 2300
    bool attachImmediately; // 起動時に即時PWM開始するか (false: コマンド受信まで回転させない)
};

class Arm {
public:
    /**
     * @brief コンストラクタ
     * @param id アーム識別ID (デフォルト: 1)
     */
    explicit Arm(int id = 1);

    /**
     * @brief アームの初期化
     * @param elevCfg 上下方向サーボの設定
     * @param gripCfg 開閉用サーボの設定
     * @param openAngle グリッパーの「開き」角度 (度)
     * @param closeAngle グリッパーの「閉じ」角度 (度)
     */
    void begin(const ArmJointConfig& elevCfg, const ArmJointConfig& gripCfg, int openAngle = 30, int closeAngle = 120);

    // 上下方向の制御
    void setElevation(int angle, float speed = -1.0f);
    void moveElevationRelative(int delta, float speed = -1.0f);
    int getElevation() const;
    int getTargetElevation() const;
    int getRawElevation() const;

    // 開閉の制御
    void setGripper(int angle, float speed = -1.0f);
    void moveGripperRelative(int delta, float speed = -1.0f);
    int getGripper() const;
    int getTargetGripper() const;
    int getRawGripper() const;

    // 2軸同時角度指定・相対移動
    void setAngles(int elevAngle, int gripAngle, float speed = -1.0f);
    void moveRelative(int deltaElev, int deltaGrip, float speed = -1.0f);

    // ゼロ点設定（現在位置を論理0度として登録）
    void setZero();
    void setZeroElevation();
    void setZeroGripper();

    // ゼロ点リセット（物理原点 0度 に戻す）
    void resetZero();
    void resetZeroElevation();
    void resetZeroGripper();

    // ゼロ点オフセット値の取得
    int getElevationZeroOffset() const;
    int getGripperZeroOffset() const;

    // 開閉ショートカット
    void openGripper(float speed = -1.0f);
    void closeGripper(float speed = -1.0f);

    // 通電・脱力（トルクON/OFF）
    void attach();
    void detach();

    // 周期更新
    void update();

    // 動作中かどうか
    bool isMoving() const;

    // 状態のシリアル出力
    void printStatus(Stream& out) const;

    int getId() const { return _id; }

private:
    int _id;
    ServoJoint _elevation;
    ServoJoint _gripper;
    int _openAngle;
    int _closeAngle;
};

#endif // ARM_H
