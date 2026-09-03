#ifndef COMMAND_PARSER_H
#define COMMAND_PARSER_H

#include <Arduino.h>
#include "Arm.h"

class CommandParser {
public:
    /**
     * @brief コンストラクタ
     * @param arm 制御対象のアームへの参照
     * @param serialPort 使用するシリアルポート (通常は Serial)
     */
    CommandParser(Arm& arm, Stream& serialPort = Serial);

    /**
     * @brief シリアル受信データのチェックとコマンド実行（loop内で毎サイクル呼び出し）
     */
    void update();

    /**
     * @brief コマンド文字列を直接パースして実行
     * @param cmd コマンド文字列
     */
    void parseAndExecute(const String& cmd);

    /**
     * @brief ヘルプメッセージの送信
     */
    void printHelp();

    /**
     * @brief ステータス情報の送信
     */
    void printStatus();

private:
    Arm& _arm;
    Stream& _serial;
    String _inputBuffer;

    void handleUpCommand(const String& params);
    void handleGripCommand(const String& params);
    void handleDualAngleCommand(int angle1, int angle2, float speed = -1.0f);
    void handleRelativeCommand(const String& params);
    bool tryParseNumbers(const String& text, int& val1, int& val2, float& val3, int& count);
};

#endif // COMMAND_PARSER_H
