#include "Arm.h"

Arm::Arm(int id)
    : _id(id)
    , _openAngle(30)
    , _closeAngle(120) {
}

void Arm::begin(const ArmJointConfig& elevCfg, const ArmJointConfig& gripCfg, int openAngle, int closeAngle) {
    _openAngle = openAngle;
    _closeAngle = closeAngle;

    _elevation.begin(
        elevCfg.pin,
        elevCfg.initAngle,
        elevCfg.minAngle,
        elevCfg.maxAngle,
        elevCfg.defaultSpeed,
        elevCfg.minPulseUs,
        elevCfg.maxPulseUs,
        elevCfg.attachImmediately
    );

    _gripper.begin(
        gripCfg.pin,
        gripCfg.initAngle,
        gripCfg.minAngle,
        gripCfg.maxAngle,
        gripCfg.defaultSpeed,
        gripCfg.minPulseUs,
        gripCfg.maxPulseUs,
        gripCfg.attachImmediately
    );
}

void Arm::setElevation(int angle, float speed) {
    _elevation.setTargetAngle(angle, speed);
}

void Arm::moveElevationRelative(int delta, float speed) {
    _elevation.moveRelative(delta, speed);
}

int Arm::getElevation() const {
    return _elevation.getCurrentAngle();
}

int Arm::getTargetElevation() const {
    return _elevation.getTargetAngle();
}

int Arm::getRawElevation() const {
    return _elevation.getRawCurrentAngle();
}

void Arm::setGripper(int angle, float speed) {
    _gripper.setTargetAngle(angle, speed);
}

void Arm::moveGripperRelative(int delta, float speed) {
    _gripper.moveRelative(delta, speed);
}

int Arm::getGripper() const {
    return _gripper.getCurrentAngle();
}

int Arm::getTargetGripper() const {
    return _gripper.getTargetAngle();
}

int Arm::getRawGripper() const {
    return _gripper.getRawCurrentAngle();
}

void Arm::setAngles(int elevAngle, int gripAngle, float speed) {
    _elevation.setTargetAngle(elevAngle, speed);
    _gripper.setTargetAngle(gripAngle, speed);
}

void Arm::moveRelative(int deltaElev, int deltaGrip, float speed) {
    _elevation.moveRelative(deltaElev, speed);
    _gripper.moveRelative(deltaGrip, speed);
}

void Arm::setZero() {
    _elevation.setZero();
    _gripper.setZero();
}

void Arm::setZeroElevation() {
    _elevation.setZero();
}

void Arm::setZeroGripper() {
    _gripper.setZero();
}

void Arm::resetZero() {
    _elevation.resetZero();
    _gripper.resetZero();
}

void Arm::resetZeroElevation() {
    _elevation.resetZero();
}

void Arm::resetZeroGripper() {
    _gripper.resetZero();
}

int Arm::getElevationZeroOffset() const {
    return _elevation.getZeroOffset();
}

int Arm::getGripperZeroOffset() const {
    return _gripper.getZeroOffset();
}

void Arm::openGripper(float speed) {
    setGripper(_openAngle, speed);
}

void Arm::closeGripper(float speed) {
    setGripper(_closeAngle, speed);
}

void Arm::attach() {
    _elevation.attach();
    _gripper.attach();
}

void Arm::detach() {
    _elevation.detach();
    _gripper.detach();
}

void Arm::update() {
    _elevation.update();
    _gripper.update();
}

bool Arm::isMoving() const {
    return _elevation.isMoving() || _gripper.isMoving();
}

void Arm::printStatus(Stream& out) const {
    out.print(F("ARM"));
    out.print(_id);
    out.print(F(" -> ELEV (D9): "));
    out.print(_elevation.getCurrentAngle());
    out.print(F(" deg"));
    if (_elevation.getZeroOffset() != 0) {
        out.print(F(" [Raw:"));
        out.print(_elevation.getRawCurrentAngle());
        out.print(F(" deg, Zero:"));
        out.print(_elevation.getZeroOffset());
        out.print(F(" deg]"));
    }
    out.print(F(" (Target: "));
    out.print(_elevation.getTargetAngle());
    out.print(F(" deg, "));
    out.print(_elevation.isAttached() ? F("ON") : F("FREE"));
    
    out.print(F("), GRIP (D10): "));
    out.print(_gripper.getCurrentAngle());
    out.print(F(" deg"));
    if (_gripper.getZeroOffset() != 0) {
        out.print(F(" [Raw:"));
        out.print(_gripper.getRawCurrentAngle());
        out.print(F(" deg, Zero:"));
        out.print(_gripper.getZeroOffset());
        out.print(F(" deg]"));
    }
    out.print(F(" (Target: "));
    out.print(_gripper.getTargetAngle());
    out.print(F(" deg, "));
    out.print(_gripper.isAttached() ? F("ON") : F("FREE"));
    
    out.print(F(") [Status: "));
    out.print(isMoving() ? F("MOVING") : F("IDLE"));
    out.println(F("]"));
}
