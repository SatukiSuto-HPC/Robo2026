# =============================================================================
# task_mode.py - アーム制御とロボットの移動シーケンス（全7ステップ）
# =============================================================================
# 【概要】
# アームの動作と、動作間に挟まる「移動（ライントレースや前進）」のタイミングを
# 明確に分離して管理するステートマシン（状態遷移）です。
# 協調型マルチタスクに組み込めるノンブロッキング設計としています。
# =============================================================================

import time

class TaskSequenceMode:
    def __init__(self, line_follower, arm_controller):
        self.lf = line_follower
        self.arm = arm_controller
        self.current_state = 0
        self.state_start_time = 0
        self.is_active = False

    def start(self):
        """シーケンスを開始する"""
        print("[TASK] 決め打ち動作シーケンスを開始します。")
        self.is_active = True
        self.transition_to("STEP_1")

    def stop(self):
        """シーケンスを強制停止する"""
        if self.is_active:
            print("[TASK] シーケンスを停止しました。")
            self.is_active = False
            self.lf.stop()

    def transition_to(self, new_state):
        """指定した状態へ遷移し、その状態の初期動作を実行する"""
        self.current_state = new_state
        self.state_start_time = time.ticks_ms()
        
        if new_state == "STEP_1":
            # 初期位置設定 ＆ 移動開始
            print("[TASK] Step 1: アーム初期位置 (0, 175) -> 荷物置き場へ移動開始")
            self.arm.set_angles(0, 175)
            self.lf.start_tracking()
            self.transition_to("WAIT_MOVE_TO_PICKUP")

        elif new_state == "WAIT_MOVE_TO_PICKUP":
            # 荷物置き場（台前）に到着するまで移動を継続する待機ステート
            pass
            
        elif new_state == "STEP_2":
            # 「台前」到着時の動作 ＆ 前進開始
            print("[TASK] Step 2: 台前到着。アーム上昇＆開放 (45, 135) -> 対象物へ前進")
            self.arm.set_angles(45, 135)
            self.lf.start_tracking() # 直進前進（運用によっては直進専用メソッドに差し替え）
            self.transition_to("WAIT_MOVE_FORWARD")

        elif new_state == "WAIT_MOVE_FORWARD":
            # 荷物を掴める位置まで前進するのを待つステート
            pass

        elif new_state == "STEP_3":
            # 前進完了、アームを降ろす
            print("[TASK] Step 3: 前進完了、停止。アーム降下＆開放 (60, 135)")
            self.lf.stop()
            self.arm.set_angles(60, 135)
            self.transition_to("WAIT_ARM_DOWN")

        elif new_state == "WAIT_ARM_DOWN":
            # アームが下がりきるまで待つ
            pass

        elif new_state == "STEP_4":
            # 荷物を掴む
            print("[TASK] Step 4: アーム閉鎖で把持 (60, 175)")
            self.arm.set_angles(60, 175)
            self.transition_to("WAIT_ARM_GRAB")

        elif new_state == "WAIT_ARM_GRAB":
            # アームが完全に閉じるまで待つ
            pass

        elif new_state == "STEP_5":
            # 荷物を持ち上げ、目的地へ移動開始
            print("[TASK] Step 5: アーム上昇＆閉鎖 (45, 175) -> 目的地へ移動開始")
            self.arm.set_angles(45, 175)
            self.lf.start_tracking()
            self.transition_to("WAIT_MOVE_TO_DROPOFF")

        elif new_state == "WAIT_MOVE_TO_DROPOFF":
            # 目的地に到着するまで移動を継続する待機ステート
            pass

        elif new_state == "STEP_6":
            # 目的地到着、荷物を放す
            print("[TASK] Step 6: 目的地到着、停止。アーム開放 (45, 135) で荷物を放す")
            self.lf.stop()
            self.arm.set_angles(45, 135)
            self.transition_to("WAIT_ARM_RELEASE")

        elif new_state == "WAIT_ARM_RELEASE":
            # 荷物を完全に放すまで待つ
            pass

        elif new_state == "STEP_7":
            # 初期状態へ復帰
            print("[TASK] Step 7: アーム初期位置 (0, 175) へ復帰 -> シーケンス完了")
            self.arm.set_angles(0, 175)
            self.is_active = False

    def update(self):
        """
        メインループから定期的に呼び出される更新処理。
        各待機ステート中に、センサー等の条件を満たしたか判定し、次のアクションへ遷移させます。
        """
        if not self.is_active:
            return
            
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self.state_start_time)
        
        # ---------------------------------------------------------
        # 【待機・移動完了の判定】
        # 現在はすべてダミーの時間（ミリ秒）で自動遷移させています。
        # 実機の運用に合わせて、「マーカー検知」「超音波センサー反応」等に書き換えてください。
        # ---------------------------------------------------------
        
        if self.current_state == "WAIT_MOVE_TO_PICKUP":
            # ---------------------------------------------------------
            # 台前に到達したか？をQRコード（UART経由）の受信で判定する
            # qrcode_uart.py はQRコードを検知すると '1' を送信します。
            # ---------------------------------------------------------
            if self.lf.last_uart_char is not None:
                if self.lf.last_uart_char == '1':
                    print("[TASK] QRコード ('1') を検知しました。台前に到着と判定します。")
                    self.lf.last_uart_char = None  # フラグをクリア
                    self.transition_to("STEP_2")
                
        elif self.current_state == "WAIT_MOVE_FORWARD":
            # 把持位置までの微速前進が終わったか？ (仮で2秒前進したら完了とする)
            if elapsed > 2000:
                self.transition_to("STEP_3")
                
        elif self.current_state == "WAIT_ARM_DOWN":
            # アームが下がりきるのを待つ (仮で1秒待機)
            if elapsed > 1000:
                self.transition_to("STEP_4")
                
        elif self.current_state == "WAIT_ARM_GRAB":
            # アームが閉じきるのを待つ (仮で1秒待機)
            if elapsed > 1000:
                self.transition_to("STEP_5")
                
        elif self.current_state == "WAIT_MOVE_TO_DROPOFF":
            # ---------------------------------------------------------
            # 降ろす目的地に到達したか？をQRコード（UART経由）の受信で判定する
            # qrcode_uart.py はQRコードを検知すると '1' を送信します。
            # ---------------------------------------------------------
            if self.lf.last_uart_char is not None:
                if self.lf.last_uart_char == '1':
                    print("[TASK] QRコード ('1') を検知しました。目的地に到着と判定します。")
                    self.lf.last_uart_char = None  # フラグをクリア
                    self.transition_to("STEP_6")
                
        elif self.current_state == "WAIT_ARM_RELEASE":
            # アームが開ききるのを待つ (仮で1秒待機)
            if elapsed > 1000:
                self.transition_to("STEP_7")
