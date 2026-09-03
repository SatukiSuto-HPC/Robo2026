#ifndef SERVO_JOINT_H
#define SERVO_JOINT_H

#include <Arduino.h>
#include <Servo.h>

class ServoJoint {
public:
    ServoJoint();

    /**
     * @brief サーボの初期化 (KRS-786ICSのパルス幅700〜2300us対応)
     * @param pin 接続ピン番号
     * @param initialAngle 初期目標角度 (0〜180)
     * @param minAngle 最小角度（リミットガード）
     * @param maxAngle 最大角度（リミットガード）
     * @param defaultSpeed デフォルト移動速度(度/秒)。0で最高速即時移動
     * @param minPulseUs 最小パルス幅 (KRS-786ICS標準: 700us)
     * @param maxPulseUs 最大パルス幅 (KRS-786ICS標準: 2300us)
     * @param attachImmediately 起動時に即座に通電・パルス出力するか (false: コマンド受信まで回転させない)
     */
    void begin(int pin, int initialAngle = 90, int minAngle = 0, int maxAngle = 180,
               float defaultSpeed = 0.0f, int minPulseUs = 700, int maxPulseUs = 2300,
               bool attachImmediately = false);

    /**
     * @brief サーボのアタッチ（PWM通電開始）
     */
    void attach();

    /**
     * @brief サーボのデタッチ（PWM停止・脱力フリー状態）
     */
    void detach();

    /**
     * @brief 目標角度（論理角度）の設定（ゼロ点オフセットが加算されます）
     * @param angle 目標角度（ゼロ点基準）
     * @param speed 移動速度(度/秒)。負の値ならbegin時のデフォルト速度を使用
     */
    void setTargetAngle(int angle, float speed = -1.0f);

    /**
     * @brief 生の物理目標角度の設定（ゼロ点オフセットを無視して直接指定）
     * @param rawAngle 物理角度（minAngle〜maxAngle）
     * @param speed 移動速度(度/秒)
     */
    void setRawTargetAngle(int rawAngle, float speed = -1.0f);

    /**
     * @brief 相対移動（現在の目標角度からの増減）
     * @param deltaAngle 増減角度（+ または -）
     * @param speed 移動速度(度/秒)
     */
    void moveRelative(int deltaAngle, float speed = -1.0f);

    /**
     * @brief 現在の角度をゼロ点（0度）として登録
     */
    void setZero();

    /**
     * @brief ゼロ点をリセット（物理原点 0度 に戻す）
     */
    void resetZero();

    /**
     * @brief ゼロ点オフセット値の取得
     */
    int getZeroOffset() const;

    /**
     * @brief 周期実行関数（ノンブロッキングで目標角度へ移動）
     */
    void update();

    /**
     * @brief 現在の論理角度（ゼロ点基準）の取得
     */
    int getCurrentAngle() const;

    /**
     * @brief 目標の論理角度（ゼロ点基準）の取得
     */
    int getTargetAngle() const;

    /**
     * @brief 生の物理現在角度（0〜180度）の取得
     */
    int getRawCurrentAngle() const;

    /**
     * @brief 生の物理目標角度（0〜180度）の取得
     */
    int getRawTargetAngle() const;

    /**
     * @brief アタッチ中（PWM出力中）かどうか
     */
    bool isAttached() const;

    /**
     * @brief 移動中かどうかの判定
     */
    bool isMoving() const;

private:
    Servo _servo;
    int _pin;
    int _minAngle;
    int _maxAngle;
    int _minPulseUs;
    int _maxPulseUs;
    int _zeroOffset;          // ゼロ点オフセット（物理角度での基準位置）
    float _currentAngle;      // 生の物理現在角度 (0〜180)
    float _targetAngle;       // 生の物理目標角度 (0〜180)
    float _defaultSpeed;
    float _speed;             // 現在の移動速度 (度/秒)
    unsigned long _lastUpdateMs;
    bool _isAttached;
    bool _hasReceivedFirstTarget;
};

#endif // SERVO_JOINT_H
