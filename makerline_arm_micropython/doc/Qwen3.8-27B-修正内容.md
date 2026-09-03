# Qwen3.8-27B 修正内容 — makerline_arm_micropython

- **調査日**: 2026-09-02
- **方法**: 静的デバッグのみ(ビルドしない・プロジェクトコードは編集していない。全ファイルの読込と、親フォルダ `makerline_arm_integration/`(Arduino 版)との突合作業)
- **対象**: `config.py` / `boot.py` / `kinematics.py` / `arm.py` / `teaching.py` / `line_follower.py` / `web_server.py` / `main.py` / `index.html`

---

## 1. ESP32 フラッシュメモリ分析(ご指定事項)

**結論: 容量は問題なし。**

| 項目 | サイズ |
|---|---|
| Python ソース計(8ファイル) | ≈ 39.4 KB |
| index.html | ≈ 9.6 KB |
| teaching.json(最大32点時) | ≲ 2 KB |
| **合計** | **≲ 51 KB** |

- MicroPython v1.x の標準レイアウト(4MB フラッシュの ESP32_GENERIC)ではユーザー用 LittleFS パーティションは約 **960KB**(実機で `os.statvfs('/')` で確認可能)。本プロジェクトはそれの **約5%** しか使用しない。
- 注意点(容量ではなく挙動):
  - MicroPython は初回 import 時に各モジュールの `.mpy` バイトコードキャッシュをフラッシュに自動生成する(+数~十数KB)。それでも余裕。
  - `teaching.py:97` — REC するたびに teaching.json を**丸ごと書き直し**。容量は無害だが、LittleFS の全ファイル再書込は主ループを数十ms ブロックし(モータ/サーボのジャudder)、頻繁な録画時はフラッシュ摩耗も多少上がる。
- ローカルの `__pycache__/`(CPython 3.11 の `.pyc`)は PC テスト産物。**ESP32 に upロードしない**(無駄な数KBを消費する)。

---

## 2. 重大(機能が無効・壊れている)

### [Critical-1] ライン追従の P 制御が完全に無効 + 補正符号が逆
**箇所**: `line_follower.py:188-196`(デッドコード)、`line_follower.py:198-202`(直行のみ)

**現状**:
- `execute_tracking_speed()` が**どこからも呼ばれていない**(grep 確認)。実際のステップ処理は常に `step_motors(True, True)` の直行 → **車は曲がらずラインを追従しない**。
- さらにこの関数の補正符号が Arduino 元版と**逆**:
  - Arduino(`LineFollower.cpp:187-192`): `leftDelay = base + correction / rightDelay = base - correction`(error>0=右にライン → 右輪を速くして右へ寄る ✓)
  - MicroPython(L191-192): `left_delay = base - correction / right_delay = base + correction`(**逆** → ラインから離れる正帰還になる)

**修正方針**:
Arduino の差分ステップ方式(`LineFollower.cpp:182-213`: minDelay でゲートし、左右の遅延差だけパルス間隔に載せる)を移植する。ただし Arduino は `delayMicroseconds` でブロックできる一方、MicroPython の協調ループではブロック睡眠を使うと他のモジュールが止まるため、**非ブロッキングな左右個別ステップスケジュール**を推奨:

```python
# execute_tracking_step を差し替え(案)
def execute_tracking_step(self):
    left_delay, right_delay = self.execute_tracking_speed()  # ← 符号は元版に合わせる
    now_us = time.ticks_us()
    if time.ticks_diff(now_us, self._left_next_step_us) >= 0:
        self.pulse_left(forward=True)
        self._left_next_step_us = now_us + left_delay
    if time.ticks_diff(now_us, self._right_next_step_us) >= 0:
        self.pulse_right(forward=True)
        self._right_next_step_us = now_us + right_delay

# execute_tracking_speed の符号修正(元版 LineFollower.cpp:187-189 と一致させる)
left_delay  = self._base_step_delay + correction   # ← 現状は - が逆
right_delay = self._base_step_delay - correction   # ← 現状は + が逆
```

`_left_next_step_us` / `_right_next_step_us` は `begin()` で初期化。これで協調ループを止めずに左右で異なる周波数を出せる。

### [Critical-2] index.html の upロード手順が README/HANDOVER に無い
**箇所**: `README.md:31-38`, `HANDOVER.md:56-64` / 起因は `web_server.py:87,90`

**現状**: `/` リクエスト時にフラッシュ上の `index.html` をストリームするが、upロード手順のファイル一覧が **8個の .py のみ**。この手順どおりに upロードするとダッシュボードが必ず **500 Error**(`os.stat('index.html')` が OSError)。

**修正**: 両ドキュメントの `ampy put` リストに `ampy put index.html` を追加(1行ずつ)。ファイル自体は存在するのでコード変更は不要。

### [Critical-3] PASSING_LINE でステップ間隔ゲートが無効 → 約2倍速で暴走
**箇所**: `line_follower.py:113-121` / 参照: Arduino `LineFollower.cpp:247`(executePassingLineStep は `_baseStepDelay` でゲート)

**現状**: `else: self.step_motors(True, True)` が毎 update()(≒0.5〜1ms間隔)で呼ばれ、`_last_step_time_us` による間隔制御が無い。マーカー通過の 600ms(`LINE_PASS_DURATION_MS`)間だけ通常速度の約2倍で前進する。

**修正**: Arduino と同じく `_last_step_time_us`(または新しいゲート変数)で `>= self._base_step_delay` になった時のみステップ:

```python
else:
    now_us = time.ticks_us()
    if time.ticks_diff(now_us, self._pass_last_step_us) >= self._base_step_delay:
        self._pass_last_step_us = now_us
        self.step_motors(True, True)
```

---

## 3. 高(安全・シーケンス整合性)

### [High-4] UART '1' が ARM_EXECUTING / PASSING_LINE を中断する
**箇所**: `line_follower.py:64-75`(受信ループ), `line_follower.py:132-134`(`start_turn_left()` がステート無視)

**現状**: アーム再生中に RPi から '1' が来ると即 TURN_LEFT 遷移。アームの待機ロジック(ARM_EXECUTING 分岐)が実行されなくなり、再生終了後も「ライン通過→追従再開」に誰も戻さない → マーカー上に停止したまま、または意図しない挙動。

**修正**: `start_turn_left()` 内で遷移元ステートをガード:

```python
def start_turn_left(self):
    if self._state in (LineFollowerState.ARM_EXECUTING, LineFollowerState.PASSING_LINE):
        print("[UART] Ignored '1' during arm/passing.")
        return
    ...
```

### [High-5] 学習点が0個でもトリガーが発火し「無言で通過」する
**箇所**: `line_follower.py:136-138`(`trigger_arm_teaching`)、`teaching.py:115-122`(`play()` が点0件で False を返す)

**現状**: `teaching.play(loop=False)` の戻り値を無視して即 ARM_EXECUTING。点が0個だと次の update で `is_playing()==False` → 何も実行せずに 600ms 前進(PASS_LINE)。警告も無い。

**修正**:

```python
def trigger_arm_teaching(self):
    if not self._teaching.play(loop=False):
        print("[LINE] No taught points. Ignoring marker line.")
        self.stop()          # または _has_triggered_on_current_line = False にして待機
        return
    self._state = LineFollowerState.ARM_EXECUTING
```

### [High-6] TURN_LEFT に最大時間タイムアウトが無い → 永遠に旋回する可能性
**箇所**: `line_follower.py:90-100` / 設定は `config.py`(未定義)

**現状**: 終了条件が `elapsed >= MIN_TURN_DURATION_MS and pattern != 0` のみ。ラインを一度も検知しない限り旋回し続ける(Arduino 元版にも無い仕様だが、実機では走行範囲外への暴走リスク)。

**修正**: `config.py` に `MAX_TURN_DURATION_MS = 5000`(妥当値は調整)を追加し、タイムアウトで強制的に停止:

```python
if elapsed >= config.MAX_TURN_DURATION_MS:
    print("[LINE] Turn timeout. Stopping.")
    self.stop()
elif elapsed >= config.MIN_TURN_DURATION_MS and self._sensor_pattern != 0:
    ...
```

---

## 4. 中(信頼性・使い勝手)

### [Medium-7] Web サーバが主ループをブロックする
**箇所**: `web_server.py:57-67`(`accept → settimeout(2.0) → _handle_client()` が同期的)

**現状**: クライアントが遅い場合、最大2秒間アーム補間・モータ駆動・他クライアント受付が停止。index.html の9.6KBストリームは低速Wi-Fiだと数百ms〜数秒かかる。ブラウザの1秒ポーリング(`index.html:173`)も毎秒この経路を踏む。

**修正方針**(軽度順):
1. 最小対応: `cl.settimeout(2.0)` → `settimeout(0.5)` に短縮し、ストリーム送出中の send もタイムアウトに耐えるよう例外で早期切断。
2. 本対応: クライアントを小型状態機械(受信バッファ蓄積→要求解析→応答)として保持し、`update()` は1回の `recv(n)` と数チャンクの `send` のみ行う非ブロッキング化。同時接続は1~2件まで制限。

### [Medium-8] HTTP 要求を1回だけ読み取る(完全受信ループなし)
**箇所**: `web_server.py:71`(単発 `recv(1024)`), `web_server.py:123,155`(body 解析)

**現状**: Content-Length を参照しないため、POST body がパケット分割されると JSON の途中切れ → `json.loads` 例外 → 何も返さず切断。小さな body ではたまたま動く。

**修正**: `Content-Length` をパースし、それだけ受信するまでループ(バッファに蓄積)。上限(例: 512B)で打ち切り。

### [Medium-9] IK + 関節制限の相互作用で「達可能なのに無反応」
**箇所**: `kinematics.py:59-96`, `arm.py:117-121` / UI: `index.html:113-124`(デフォルト x=120, y=80)

**現状**: `move_to()` は elbow_up 解のみ試し、`is_angles_valid`(0〜180°)に落ちると False。ダッシュボードの**デフォルト目標 (120, 80)**(r≈144mm < 最大リーチ200mm で幾何学的には達可能)は t1≈-46° になり拒否され、**MOVE ボタンが何もせずに終わる**。参考: HOME(90°,90°)の FK は (-100, +100)。

**修正方針**:
1. `move_to()` で elbow_up が無効なら elbow_down も試し、両方無効の場合のみ False。
2. Web API `/api/command` の MOVE 応答を `{"status":"ok"}` → 達可能/不可(理由付き)に変え、UI に表示。

### [Medium-10] STOP が進行中のアーム運動を止めない
**箇所**: `teaching.py:133-135`(`stop()` はステートのみ IDLE), `web_server.py:129-131`

**現状**: Web の STOP でトラッキングと再生は止まるが、アームは最後の目標点まで動き続ける。

**修正方針**: 意図次第。即停止を望むなら arm.py に `stop_motion()`(現在位置で `_is_moving=False` 化+PWM書き込み)を追加し、teaching.stop() から呼ぶ。継続が意図的ならドキュメントに明記のみ。

### [Medium-11] プライベート属性への直接アクセス
**箇所**: `teaching.py:87-88`(`hasattr(self._arm, 'getCurrentTheta1')` は常に False → `_current_theta1` にフォールバック)

**修正**: arm.py に公開ゲッタを追加し、teaching 側をそれへ統一:

```python
# arm.py
def get_theta1(self): return self._current_theta1
def get_theta2(self): return self._current_theta2
```

---

## 5. 軽微・衛生面

| # | 箇所 | 内容 | 修正方針 |
|---|---|---|---|
| L-1 | `boot.py:26` | `authmode=0` は MicroPython の WLAN.config に文書化されたキーでなく、無視される no-op。パスワード未設定の AP はデフォルトでオープンなので結果は期待どおり | 実機確認後に不要なら削除(または `security=` 指定に置換) |
| L-2 | `arm.py:49-59` | `attach_servos()` が既存 PWM を deinit せず新規作成(SERVO_ON 連打で重複チャネルの恐れ) | attach 前に該当ピンの旧 PWM を deinit、または `_is_attached` で早期 return |
| L-3 | `arm.py:194-195` | オフセットで duty が [1638..7864] 外に出てもクランプなし | `max(1638, min(7864, duty))` でクランプ |
| L-4 | `line_follower.py:37` | `hasattr(config, 'DIR_PIN')` は常に False のデッドチェック | `config.LEFT_DIR_PIN` に直接変更 |
| L-5 | `config.py:74` | `SERIAL_BAUDRATE = 9600` が未使用(UART は `RPI_UART_BAUDRATE`) | 削除または統一 |
| L-6 | `index.html:62` | サーボ表示が初回ポーリングまで "ON" と誤表示(実際は OFF) | 初期値を "OFF" に変更 |
| L-7 | `main.py:56-58` | 例外ループが 0.1s スリープで無限リトライ(致命的な初期化失敗時はブートループの可能性) | 連続例外カウントで N 回後に安全停止・再起動の検討 |
| L-8 | `__pycache__/` | CPython 3.11 の `.pyc`(PC テスト産物)。ESP32 upロード対象外 | upロード手順から除外(現状は README に無いため問題なし。誤 upロードに注意) |

---

## 6. 優先度まとめ

| 優先 | # | 問題 | 影響 |
|---|---|---|---|
| Critical | 1 | P制御がデッドコード+符号逆転 | **ライン追従機能そのものが無効** |
| Critical | 2 | index.html upロード手順欠落 | **ダッシュボードが500で開けない** |
| Critical | 3 | PASSING_LINE の高速暴走 | 走行安全 |
| High | 4 | UART がアーム実行中を中断 | シーケンス整合性・安全 |
| High | 5 | 無点数トリガーの無言通過 | 意図しない動作 |
| High | 6 | TURN_LEFT のタイムアウト欠如 | 暴走リスク |
| Medium | 7-8 | Web サーバのブロッキング/不完全受信 | リアルタイム性・信頼性 |
| Medium | 9-11 | IK 拒否 / STOP 挙動 / プライベートアクセス | 使い勝手・保守性 |

フラッシュメモリは約960KBに対し使用≲51KBで**問題なし**。上記の機能バグ、特に [Critical-1] と [Critical-2] を潰さないと実機では「直進するだけ・ダッシュボードが開かない」状態になります。
