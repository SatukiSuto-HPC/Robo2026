#include "ServoJoint.h"
#include <math.h>

ServoJoint::ServoJoint()
    : _pin(-1)
    , _minAngle(0)
    , _maxAngle(180)
    , _minPulseUs(700)
    , _maxPulseUs(2300)
    , _zeroOffset(0)
    , _currentAngle(90.0f)
    , _targetAngle(90.0f)
    , _defaultSpeed(0.0f)
    , _speed(0.0f)
    , _lastUpdateMs(0)
    , _isAttached(false)
    , _hasReceivedFirstTarget(false) {
}

void ServoJoint::begin(int pin, int initialAngle, int minAngle, int maxAngle,
                       float defaultSpeed, int minPulseUs, int maxPulseUs,
                       bool attachImmediately) {
    _pin = pin;
    _minAngle = minAngle;
    _maxAngle = maxAngle;
    _minPulseUs = minPulseUs;
    _maxPulseUs = maxPulseUs;
    _zeroOffset = 0;
    _defaultSpeed = defaultSpeed;
    _speed = defaultSpeed;

    _targetAngle = constrain(initialAngle, _minAngle, _maxAngle);
    _currentAngle = _targetAngle;
    _lastUpdateMs = millis();

    // 起動時に勝手に回転しないよう、デフォルトでは未アタッチ（PWM信号を出さない）
    if (attachImmediately && _pin >= 0) {
        attach();
        int pulseUs = map((int)_currentAngle, _minAngle, _maxAngle, _minPulseUs, _maxPulseUs);
        _servo.writeMicroseconds(pulseUs);
        _hasReceivedFirstTarget = true;
    } else {
        _isAttached = false;
        _hasReceivedFirstTarget = false;
    }
}

void ServoJoint::attach() {
    if (!_isAttached && _pin >= 0) {
        _servo.attach(_pin, _minPulseUs, _maxPulseUs);
        _isAttached = true;
        _lastUpdateMs = millis();
    }
}

void ServoJoint::detach() {
    if (_isAttached) {
        _servo.detach();
        _isAttached = false;
    }
}

void ServoJoint::setTargetAngle(int angle, float speed) {
    // 論理角度にゼロ点オフセットを加算して物理角度に変換
    setRawTargetAngle(angle + _zeroOffset, speed);
}

void ServoJoint::setRawTargetAngle(int rawAngle, float speed) {
    _targetAngle = constrain(rawAngle, _minAngle, _maxAngle);

    // 初めてコマンドを受信した際の初期化
    if (!_hasReceivedFirstTarget) {
        _hasReceivedFirstTarget = true;
        _currentAngle = _targetAngle;
        attach();
        int pulseUs = map((int)_currentAngle, _minAngle, _maxAngle, _minPulseUs, _maxPulseUs);
        _servo.writeMicroseconds(pulseUs);
        return;
    }

    if (!_isAttached) {
        attach();
    }

    if (speed < 0.0f) {
        _speed = _defaultSpeed;
    } else {
        _speed = speed;
    }

    // 速度が0以下の場合は即座に目標角度に移動
    if (_speed <= 0.0f) {
        _currentAngle = _targetAngle;
        int pulseUs = map((int)_currentAngle, _minAngle, _maxAngle, _minPulseUs, _maxPulseUs);
        _servo.writeMicroseconds(pulseUs);
    }
}

void ServoJoint::moveRelative(int deltaAngle, float speed) {
    // 現在の目標物理角度に対して増減
    setRawTargetAngle(round(_targetAngle) + deltaAngle, speed);
}

void ServoJoint::setZero() {
    // 現在の物理角度を新しいゼロ点オフセットとして登録
    _zeroOffset = round(_currentAngle);
}

void ServoJoint::resetZero() {
    _zeroOffset = 0;
}

int ServoJoint::getZeroOffset() const {
    return _zeroOffset;
}

void ServoJoint::update() {
    if (!_isAttached) return;

    // 即時移動モードの場合は既に反映済み
    if (_speed <= 0.0f || fabsf(_currentAngle - _targetAngle) < 0.01f) {
        return;
    }

    unsigned long now = millis();
    float dt = (now - _lastUpdateMs) / 1000.0f;
    _lastUpdateMs = now;

    // ガード処理（最大0.1秒扱い）
    if (dt > 0.1f) {
        dt = 0.1f;
    }

    float step = _speed * dt;
    if (_currentAngle < _targetAngle) {
        _currentAngle += step;
        if (_currentAngle > _targetAngle) {
            _currentAngle = _targetAngle;
        }
    } else if (_currentAngle > _targetAngle) {
        _currentAngle -= step;
        if (_currentAngle < _targetAngle) {
            _currentAngle = _targetAngle;
        }
    }

    int pulseUs = map((int)round(_currentAngle), _minAngle, _maxAngle, _minPulseUs, _maxPulseUs);
    _servo.writeMicroseconds(pulseUs);
}

int ServoJoint::getCurrentAngle() const {
    // 論理角度（ゼロ点基準）
    return round(_currentAngle) - _zeroOffset;
}

int ServoJoint::getTargetAngle() const {
    // 論理目標角度（ゼロ点基準）
    return round(_targetAngle) - _zeroOffset;
}

int ServoJoint::getRawCurrentAngle() const {
    // 生の物理現在角度
    return round(_currentAngle);
}

int ServoJoint::getRawTargetAngle() const {
    // 生の物理目標角度
    return round(_targetAngle);
}

bool ServoJoint::isAttached() const {
    return _isAttached;
}

bool ServoJoint::isMoving() const {
    if (!_isAttached) return false;
    return fabsf(_currentAngle - _targetAngle) >= 1.0f;
}
