# =============================================================================
# main.py - メインイベントループ / 協調型マルチタスク (ESP32 MicroPython用)
# =============================================================================
# 【概要】
# 本スクリプトは、ESP32上で動作する自律走行搬送ロボット（MakerLine仕様）の
# メインエントリーポイントです。
#
# FreeRTOSやタイマー割り込みによる複雑なマルチスレッドを使わず、
# 各モジュールをノンブロッキング（非ブロッキング）で巡回実行する
# 「協調型マルチタスク（Cooperative Multitasking）」アーキテクチャを採用しています。
#
# 【主な構成モジュール】
# 1. LineFollower (line_follower.py):
#    - 4つのデジタルラインセンサを用いた黒線トレース制御
#    - DRV8825ステッピングモータードライバへのマイクロ秒単位のパルス生成
#    - 交差点・マーカー検知、旋回、自律走行ステートマシン管理
# 2. WebServer (web_server.py):
#    - Wi-Fi AP/STAモードでの非同期Webサーバー (ポート80)
#    - ブラウザUIからの走行開始/停止、パラメータ調整、ステータス監視
# =============================================================================

import time  # 時間計測およびウェイト（sleep）用標準モジュール
# 自作制御モジュールのインポート
from line_follower import LineFollower  # ライントレース・モーター駆動制御クラス
from web_server import WebServer        # ブラウザ操作用ノンブロッキングWebサーバークラス
from uart_receiver import UartEventReceiver
from task_mode import TaskSequenceMode
from a_mu import ArmController


def main():
    """
    アプリケーションのメイン関数
    各モジュールの初期化を行い、無限ループによる協調マルチタスクを実行します。
    """
    print("[INIT] Starting MakerLine MicroPython Controller...")

    # -------------------------------------------------------------------------
    # 1. モジュールのインスタンス化 (Module Instantiation)
    # -------------------------------------------------------------------------
    # ライントレース制御クラスのインスタンスを生成（モーター・センサの論理初期化）
    line_follower = LineFollower()
    uart_receiver = UartEventReceiver()
    arm_controller = ArmController()
    if not arm_controller.begin():
        print("[INIT ERROR] Arduino arm UART is unavailable. Stopping startup.")
        return

    # Webサーバーのインスタンス生成
    # ※WebブラウザUIから走行状態の変更やパラメータ操作ができるよう、
    #   line_follower インスタンスへの参照を渡しています。
    web_server = WebServer(line_follower)

    task_mode = TaskSequenceMode(line_follower, arm_controller, uart_receiver)

    # -------------------------------------------------------------------------
    # 2. ハードウェア・ペリフェラルの初期化と通信開始 (Begin Hardware)
    # -------------------------------------------------------------------------
    # GPIOピンの入出力設定、モーター初期状態の設定、タイマー等の開始
    line_follower.begin()

    # Wi-Fiソケットの作成とバインド、HTTPリスニング待機状態への遷移
    web_server.begin()

    print("[MAIN LOOP] Entering cooperative multitasking loop...")

    # -------------------------------------------------------------------------
    # 3. メイン協調ループ (Main Cooperative Event Loop)
    # -------------------------------------------------------------------------
    # 各タスクの .update() を高速に順次呼び出すことで、擬似的な並行処理を実現します。
    # すべての .update() はブロックせず（ノンブロッキング）、即座に制御を返します。
    while True:
        try:
            # --- タスク1: ライントレース制御・センサ読み取り ---
            # センサ値の取得、ステートマシン更新、ステッピングモーターのパルス出力を行います。
            uart_receiver.update()
            task_mode.update()
            line_follower.update()
            arm_controller.update()

            # --- タスク2: Webサーバーのリクエスト処理 ---
            # クライアントからの接続要求やHTTPリクエスト（REST API・UI画面配信）をノンブロッキングで処理します。
            web_server.update()

            # --- タスク4: CPU資源の譲渡（Cooperative Yield） ---
            # マイコンのバックグラウンド処理（Wi-FiスタックやGC等）が詰まるのを防ぐため、
            # 微小なスリープを挟んでCPU資源を譲渡（yield）します。
            #
            # 【重要: タイミング最適化の理由】
            # - アイドル状態 (STATE_IDLE == 0):
            #   モーターが停止しているため、10ms程度のスリープを入れてCPU負荷を大幅に下げ、
            #   消費電力を抑えつつWebサーバーやWi-Fiスタックの安定性を高めます。
            # - 走行・トレース中 (TRACKING等):
            #   ステッピングモーターのパルス間隔（マイクロ秒単位）の乱れを防ぐため、
            #   最小限の10μsスリープのみを挟み、最大ループ速度を維持します。
            if line_follower.get_state() == 0 and not task_mode.is_active:  # 停止/待機中
                time.sleep_ms(10)  # 10ミリ秒スリープ（省電力・他処理優先）
            else:
                time.sleep_us(10)  # 10マイクロ秒スリープ（高精度パルス生成優先）

        except KeyboardInterrupt:
            # 開発中にシリアルコンソールから Ctrl+C が入力された場合の安全停止処理
            print("[MAIN] Interrupted by user. Stopping cart.")
            line_follower.stop()  # モーターを急停止させ、安全を確保
            break                 # メインループを抜けて終了

        except Exception as e:
            # ループ内で予期せぬ例外が発生しても、即座にマイコン全体がクラッシュ・停止しないよう捕捉
            print(f"[MAIN ERROR] {e}")
            # エラーログがコンソールを埋め尽くす（ログストーム）のを防ぐため、わずかに待機
            time.sleep(0.1)


# -----------------------------------------------------------------------------
# スクリプト直接実行時のエントリーポイント
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    main()

