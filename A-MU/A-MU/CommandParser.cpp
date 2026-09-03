#include "CommandParser.h"
#include <stdlib.h>
#include <string.h>

CommandParser::CommandParser(Arm& arm, Stream& serialPort)
    : _arm(arm)
    , _serial(serialPort) {
    _inputBuffer.reserve(64);
}

void CommandParser::update() {
    while (_serial.available() > 0) {
        char c = (char)_serial.read();
        
        if (c == '\n' || c == '\r') {
            if (_inputBuffer.length() > 0) {
                _inputBuffer.trim();
                if (_inputBuffer.length() > 0) {
                    parseAndExecute(_inputBuffer);
                }
                _inputBuffer = "";
            }
        } else {
            if (_inputBuffer.length() < 64) {
                _inputBuffer += c;
            }
        }
    }
}

void CommandParser::parseAndExecute(const String& rawCmd) {
    String cmd = rawCmd;
    cmd.trim();
    String upperCmd = cmd;
    upperCmd.toUpperCase();

    if (upperCmd.length() == 0) return;

    // 接頭辞（ARM: や ARM1:）があれば除去
    if (upperCmd.startsWith("ARM:") || upperCmd.startsWith("ARM1:") || upperCmd.startsWith("ARM2:")) {
        int idx = upperCmd.indexOf(':');
        upperCmd = upperCmd.substring(idx + 1);
    }

    // 1. システム & ゼロ点コマンド
    if (upperCmd == "HELP" || upperCmd == "?") {
        printHelp();
        return;
    }
    if (upperCmd == "STATUS") {
        printStatus();
        return;
    }
    if (upperCmd == "ZERO" || upperCmd == "TARE" || upperCmd == "SETZERO") {
        _arm.setZero();
        _serial.println(F("OK: Current angles set as ZERO (0 deg origin) for all servos"));
        printStatus();
        return;
    }
    if (upperCmd == "ZERO:S1" || upperCmd == "ZERO:UP" || upperCmd == "ZERO:ELEV") {
        _arm.setZeroElevation();
        _serial.println(F("OK: Servo 1 current angle set as ZERO"));
        return;
    }
    if (upperCmd == "ZERO:S2" || upperCmd == "ZERO:GRIP") {
        _arm.setZeroGripper();
        _serial.println(F("OK: Servo 2 current angle set as ZERO"));
        return;
    }
    if (upperCmd == "ORIGIN" || upperCmd == "RESET_ZERO" || upperCmd == "RESETZERO") {
        _arm.resetZero();
        _serial.println(F("OK: Zero offsets RESET to physical origin (0-180 deg)"));
        printStatus();
        return;
    }
    if (upperCmd == "FREE" || upperCmd == "DETACH" || upperCmd == "OFF") {
        _arm.detach();
        _serial.println(F("OK: SERVOS DETACHED (FREE)"));
        return;
    }
    if (upperCmd == "ATTACH" || upperCmd == "ON") {
        _arm.attach();
        _serial.println(F("OK: SERVOS ATTACHED (TORQUE ON)"));
        return;
    }
    if (upperCmd == "OPEN") {
        _arm.openGripper();
        _serial.println(F("OK: GRIPPER OPENED"));
        return;
    }
    if (upperCmd == "CLOSE") {
        _arm.closeGripper();
        _serial.println(F("OK: GRIPPER CLOSED"));
        return;
    }

    // 2. 相対移動コマンド: REL:10:-5, REL:10:-5:30, R:10:-5
    if (upperCmd.startsWith("REL:") || upperCmd.startsWith("R:")) {
        int colon = upperCmd.indexOf(':');
        handleRelativeCommand(upperCmd.substring(colon + 1));
        return;
    }

    // 3. サーボ1 (D9: 上下方向) 角度指定: S1, ELEV, UP, D9
    if (upperCmd.startsWith("UP:") || upperCmd.startsWith("ELEV:") || 
        upperCmd.startsWith("S1:") || upperCmd.startsWith("SERVO1:") || upperCmd.startsWith("D9:")) {
        int colon = upperCmd.indexOf(':');
        handleUpCommand(cmd.substring(colon + 1));
        return;
    }

    // 4. サーボ2 (D10: 開閉) 角度指定: GRIP, S2, SERVO2, D10
    if (upperCmd.startsWith("GRIP:") || upperCmd.startsWith("S2:") || 
        upperCmd.startsWith("SERVO2:") || upperCmd.startsWith("D10:")) {
        int colon = upperCmd.indexOf(':');
        handleGripCommand(cmd.substring(colon + 1));
        return;
    }

    // 5. 2軸同時の角度指定: POS:90:45, SET:90:45, ANGLE:90:45
    if (upperCmd.startsWith("POS:") || upperCmd.startsWith("SET:") || 
        upperCmd.startsWith("ANGLE:") || upperCmd.startsWith("ANGLES:")) {
        int colon = upperCmd.indexOf(':');
        String params = upperCmd.substring(colon + 1);
        int v1 = 0, v2 = 0;
        float v3 = -1.0f;
        int count = 0;
        if (tryParseNumbers(params, v1, v2, v3, count) && count >= 2) {
            handleDualAngleCommand(v1, v2, v3);
            return;
        }
    }

    // 6. 数値直接送信 (例: "90,45" や "90:45" や "90,45,30")
    int val1 = 0, val2 = 0;
    float val3 = -1.0f;
    int count = 0;
    if (tryParseNumbers(cmd, val1, val2, val3, count)) {
        if (count == 1) {
            // 数値1つの場合は上下角度として設定
            handleDualAngleCommand(val1, _arm.getGripper());
            return;
        } else if (count >= 2) {
            // 数値2つ以上の場合は (サーボ1角度, サーボ2角度, [速度])
            handleDualAngleCommand(val1, val2, val3);
            return;
        }
    }

    // 未知のコマンド
    _serial.print(F("ERR: Unknown command: "));
    _serial.println(rawCmd);
    _serial.println(F("Type 'HELP' for available commands."));
}

bool CommandParser::tryParseNumbers(const String& text, int& val1, int& val2, float& val3, int& count) {
    count = 0;
    char buffer[64];
    text.toCharArray(buffer, sizeof(buffer));

    // 区切り文字: カンマ, コロン, 空白, セミコロン
    char* token = strtok(buffer, ",: ;");
    if (!token) return false;

    val1 = atoi(token);
    count++;

    token = strtok(NULL, ",: ;");
    if (token) {
        val2 = atoi(token);
        count++;

        token = strtok(NULL, ",: ;");
        if (token) {
            val3 = atof(token);
            count++;
        }
    }

    return true;
}

void CommandParser::handleUpCommand(const String& params) {
    String p = params;
    p.trim();
    if (p.length() == 0) {
        _serial.println(F("ERR: Missing angle for UP/S1 command (e.g. S1:90 or S1:+10 or UP:90:30)"));
        return;
    }

    int colon = p.indexOf(':');
    if (colon == -1) colon = p.indexOf(',');

    String angleStr = (colon == -1) ? p : p.substring(0, colon);
    float speed = (colon == -1) ? -1.0f : p.substring(colon + 1).toFloat();
    angleStr.trim();

    // 先頭が '+' または '-' の場合は相対移動
    if (angleStr.startsWith("+") || angleStr.startsWith("-")) {
        int delta = angleStr.toInt();
        _arm.moveElevationRelative(delta, speed);
        _serial.print(F("OK: Servo 1 (Elevation) Relative -> "));
        if (delta > 0) _serial.print('+');
        _serial.print(delta);
        _serial.print(F(" deg (Current: "));
        _serial.print(_arm.getElevation());
        _serial.println(F(" deg)"));
    } else {
        int angle = angleStr.toInt();
        _arm.setElevation(angle, speed);
        _serial.print(F("OK: Servo 1 (Elevation D9) -> "));
        _serial.print(angle);
        _serial.print(F(" deg"));
        if (speed > 0) {
            _serial.print(F(" @ "));
            _serial.print(speed);
            _serial.print(F(" deg/s"));
        }
        _serial.println();
    }
}

void CommandParser::handleGripCommand(const String& params) {
    String p = params;
    p.trim();
    if (p.length() == 0) {
        _serial.println(F("ERR: Missing angle for GRIP/S2 command (e.g. S2:45 or S2:+5 or GRIP:45:30)"));
        return;
    }

    int colon = p.indexOf(':');
    if (colon == -1) colon = p.indexOf(',');

    String angleStr = (colon == -1) ? p : p.substring(0, colon);
    float speed = (colon == -1) ? -1.0f : p.substring(colon + 1).toFloat();
    angleStr.trim();

    // 先頭が '+' または '-' の場合は相対移動
    if (angleStr.startsWith("+") || angleStr.startsWith("-")) {
        int delta = angleStr.toInt();
        _arm.moveGripperRelative(delta, speed);
        _serial.print(F("OK: Servo 2 (Gripper) Relative -> "));
        if (delta > 0) _serial.print('+');
        _serial.print(delta);
        _serial.print(F(" deg (Current: "));
        _serial.print(_arm.getGripper());
        _serial.println(F(" deg)"));
    } else {
        int angle = angleStr.toInt();
        _arm.setGripper(angle, speed);
        _serial.print(F("OK: Servo 2 (Gripper D10) -> "));
        _serial.print(angle);
        _serial.print(F(" deg"));
        if (speed > 0) {
            _serial.print(F(" @ "));
            _serial.print(speed);
            _serial.print(F(" deg/s"));
        }
        _serial.println();
    }
}

void CommandParser::handleDualAngleCommand(int angle1, int angle2, float speed) {
    _arm.setAngles(angle1, angle2, speed);

    _serial.print(F("OK: Angles Set -> S1(D9): "));
    _serial.print(angle1);
    _serial.print(F(" deg, S2(D10): "));
    _serial.print(angle2);
    _serial.print(F(" deg"));
    if (speed > 0) {
        _serial.print(F(" @ "));
        _serial.print(speed);
        _serial.print(F(" deg/s"));
    }
    _serial.println();
}

void CommandParser::handleRelativeCommand(const String& params) {
    int v1 = 0, v2 = 0;
    float v3 = -1.0f;
    int count = 0;
    if (tryParseNumbers(params, v1, v2, v3, count) && count >= 2) {
        _arm.moveRelative(v1, v2, v3);
        _serial.print(F("OK: Relative Move -> S1: "));
        if (v1 > 0) _serial.print('+');
        _serial.print(v1);
        _serial.print(F(" deg (Now: "));
        _serial.print(_arm.getElevation());
        _serial.print(F(" deg), S2: "));
        if (v2 > 0) _serial.print('+');
        _serial.print(v2);
        _serial.print(F(" deg (Now: "));
        _serial.print(_arm.getGripper());
        _serial.println(F(" deg)"));
    } else {
        _serial.println(F("ERR: Invalid format for REL command (e.g. REL:10:-5 or REL:10:-5:30)"));
    }
}

void CommandParser::printHelp() {
    _serial.println(F("--- Kondo KRS-786ICS Arm Control Commands ---"));
    _serial.println(F(" [Servo 1: Elevation (D9)]"));
    _serial.println(F("  S1:<angle> / UP:<angle>         : Set angle (e.g. S1:90 or UP:90)"));
    _serial.println(F("  S1:+<deg> / S1:-<deg>           : Relative move (e.g. S1:+10 or S1:-15)"));
    _serial.println(F("  S1:<angle>:<speed>              : Set angle with speed in deg/s (e.g. S1:90:30)"));
    _serial.println(F(" [Servo 2: Gripper (D10)]"));
    _serial.println(F("  S2:<angle> / GRIP:<angle>       : Set angle (e.g. S2:45 or GRIP:45)"));
    _serial.println(F("  S2:+<deg> / S2:-<deg>           : Relative move (e.g. S2:+5 or S2:-10)"));
    _serial.println(F("  OPEN / CLOSE                    : Open/Close gripper shortcut"));
    _serial.println(F(" [Simultaneous 2-Servo Control]"));
    _serial.println(F("  POS:<angle1>:<angle2>           : Set both angles (e.g. POS:90:45)"));
    _serial.println(F("  REL:<delta1>:<delta2>           : Move both relatively (e.g. REL:10:-5)"));
    _serial.println(F("  <angle1>,<angle2>               : Direct numbers (e.g. 90,45 or 90 45)"));
    _serial.println(F(" [Zero-Point & System Commands]"));
    _serial.println(F("  ZERO / TARE                     : Set CURRENT angles as ZERO (0 deg origin)"));
    _serial.println(F("  ORIGIN / RESET_ZERO             : Reset zero-point to physical 0-180 deg"));
    _serial.println(F("  FREE / DETACH                   : Turn off torque (free movement)"));
    _serial.println(F("  ATTACH / ON                     : Turn on torque"));
    _serial.println(F("  STATUS                          : Show current angles, zero offsets, and state"));
    _serial.println(F("  HELP                            : Show this help message"));
    _serial.println(F("---------------------------------------------"));
}

void CommandParser::printStatus() {
    _serial.println(F("--- Arm Controller Status ---"));
    _arm.printStatus(_serial);
    _serial.println(F("-----------------------------"));
}
