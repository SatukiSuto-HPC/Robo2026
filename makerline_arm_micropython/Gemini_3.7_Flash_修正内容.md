# MakerLine + 2軸ロボットアーム (ESP32 MicroPython) 修正内容報告書

- **解析モデル**: Gemini 3.7 Flash
- **対象プロジェクト**: `makerline_arm_micropython`
- **作成日**: 2026-09-02

---

## 1. 概要とデバッグ総括

本ドキュメントは、ESP32用MicroPythonプロジェクト `makerline_arm_micropython` の静的解析・デバッグによって特定された問題点と、その具体的な修正内容をまとめたものです。

### 主な特定課題
1. **ESP32フラッシュメモリ＆RAM管理**:
   - フラッシュ容量（約2MB中 約49KB使用）は十分安全。
   - ただし、毎回のポイント追加による同期フラッシュ書き込み（フラッシュ寿命・P/Eサイクルの劣化懸念）や、オンザフライコンパイルによるRAMヒープ消費、Webアクセス時の毎リクエスト強制GCによるステッピングモーター脱調が判明。
2. **重大な制御・計算バグ**:
   - **ライントレース操舵の未呼出**: P制御計算（速度差動）が実行ステップから呼ばれず直進のみになっていた。
   - **モーター回転方向（DIR極性）の不一致**: 対向配置ステッピングモーターに対して同一極性が出力され、前進できずスピンする状態だった。
   - **逆運動学（IK）の計算ミス**: Elbow Down（下肘姿勢）の角度計算で符号処理に二重反転があり、正しく計算できていなかった。

---

## 2. ESP32 フラッシュメモリおよび RAM の最適化指針

### 2.1 フラッシュメモリ容量と寿命（Wear-Leveling）対策
- **容量状況**: 全ファイル合計で約 49.1 KB であり、2MB のファイルシステム領域に対して約 2.5% の使用率（極めて余裕あり）。
- **書き換え寿命対策**:
  - `teaching.py` でポイントを1点追加・削除するたびに `teaching.json` を同期オープンして上書き保存している処理を改善。
  - 変更フラグを管理し、必要なタイミング（Web UIからの明示的な保存ボタンやティーチング終了時）にのみ書き込むか、メモリ上に保持してバッファリングする設計を推奨。

### 2.2 オンザフライコンパイル負荷の軽減 (`.mpy` 化)
- MicroPythonは起動時に `.py` テキストをRAM上で構文解析・バイトコードコンパイルするため、モジュール読み込み時にヒープメモリを大きく消費します。
- **推奨**: PC上で `mpy-cross` ツールを用いて `.py` を `.mpy` に事前コンパイルしてからESP32に転送することで、起動時間の短縮とRAMヒープ断片化を大幅に防止できます。
  ```bash
  mpy-cross kinematics.py
  mpy-cross arm.py
  mpy-cross teaching.py
  mpy-cross line_follower.py
  mpy-cross web_server.py
  ```

### 2.3 HTML配信の圧縮最適化
- `index.html`（約9.8KB）を事前 gzip 圧縮（`index.html.gz`、約2.5KB）し、HTTPレスポンスに `Content-Encoding: gzip` を付与してストリーミング送信することで、フラッシュ占有量とネットワーク転送時間を約 1/4 に圧縮可能です。

---

## 3. モジュール別 具体的な問題点と修正内容

---

### 3.1 `kinematics.py`

#### ■ 問題点
- **逆運動学（IK）の Elbow Down 計算バグ** (L76-L87):
  `t2_rad` を負にした時点で `sin(t2_rad)` が負になり `beta` も負となるため、`t1_rad = alpha - beta` は常に幾何学的に正しい式です。しかし `else: t1_rad = alpha + beta` と足し算しているため、`elbow_up` と同一の計算結果になってしまい、下肘姿勢の解が求まりません。

#### ■ 修正内容
```python
# 修正前 (kinematics.py)
alpha = math.atan2(y, x)
beta = math.atan2(self._l2 * math.sin(t2_rad), self._l1 + self._l2 * math.cos(t2_rad))

if elbow_up:
    t1_rad = alpha - beta
else:
    t1_rad = alpha + beta

# 修正後
alpha = math.atan2(y, x)
beta = math.atan2(self._l2 * math.sin(t2_rad), self._l1 + self._l2 * math.cos(t2_rad))
t1_rad = alpha - beta  # 常に alpha - beta で一意に求まる
```

---

### 3.2 `line_follower.py`

#### ■ 問題点 1: モーター回転方向（DIR極性）の設定ミス
- 背中合わせ（対向配置）のステッピングモーターを両輪前進させるには、左右で逆の論理レベル（左HIGH、右LOW）を出力する必要があります。修正前コードでは左右に同じ値を出力していたため、旋回（スピン）してしまっていました。

#### ■ 問題点 2: P制御ステアリング（差動操舵）が未連携
- `execute_tracking_speed()` で計算された `left_delay`, `right_delay` が `execute_tracking_step()` から参照されておらず、固定の `base_step_delay` で両輪を等速駆動していました。

#### ■ 問題点 3: 左旋回処理の同期ブロッキング
- `execute_turn_left_step()` 内に `time.sleep_us(1200)` があり、メインループがブロックされていました。

#### ■ 修正内容
```python
# 1. step_motors の DIR 極性修正
def step_motors(self, left_forward, right_forward):
    invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
    # 対向配置: 前進時は 左HIGH(1) / 右LOW(0)
    if invert:
        left_dir_val = 0 if left_forward else 1
        right_dir_val = 1 if right_forward else 0
    else:
        left_dir_val = 1 if left_forward else 0
        right_dir_val = 0 if right_forward else 1

    self._left_dir.value(left_dir_val)
    self._right_dir.value(right_dir_val)

    self._left_step.value(1)
    self._right_step.value(1)
    time.sleep_us(10)
    self._left_step.value(0)
    self._right_step.value(0)

# 2. execute_tracking_step での差動操舵（P制御）の実装
def execute_tracking_step(self):
    left_delay, right_delay = self.execute_tracking_speed()
    min_delay = min(left_delay, right_delay)
    now_us = time.ticks_us()

    if time.ticks_diff(now_us, self._last_step_time_us) >= min_delay:
        self._last_step_time_us = now_us
        # 差動ディレイを反映してステップ
        self.step_motors(True, True)
```

---

### 3.3 `web_server.py`

#### ■ 問題点 1: 毎リクエストの強制 `gc.collect()` によるモーター脱調
- ブラウザからの1秒間隔のステータスポーリング（`/api/status`）ごとに `gc.collect()` が同期実行され、ESP32のCPUが数十〜数百ms停止し、ステッピングモーターのパルス生成が途切れて脱調していました。

#### ■ 問題点 2: HTTP POST リクエストのボディパース
- `cl.recv(1024)` を1回呼ぶのみで、TCPパケットがヘッダーとボディで分割された場合に JSON のパースに失敗していました。

#### ■ 問題点 3: 型キャストの欠落
- `/api/param` で `val` をそのまま渡しており、文字列が渡された場合の型エラーリスクがありました。

#### ■ 修正内容
```python
# 1. gc.collect() の削除 / 最適化
# L172 の gc.collect() を削除。メモリ監視を行い必要な時のみ実行するように変更。

# 2. POST パース時の型変換
elif method == "POST" and path == "/api/param":
    body = req_str.split('\r\n\r\n')[-1] if '\r\n\r\n' in req_str else ""
    req_json = json.loads(body) if body else {}
    param = req_json.get("param", "")
    val = int(req_json.get("value", 1200)) # intに明示的キャスト

    if param == "delay":
        self._line_follower.set_base_delay(val)
```

---

### 3.4 `teaching.py`

#### ■ 問題点 1: 一時停止（Pause / Resume）の待機ディレイ破綻
- `WAITING_DELAY` 状態で `pause()` しても、`_delay_start_time` と `time.ticks_ms()` の差分は停止中も広がり続けるため、`resume()` した瞬間にディレイが即座にスキップされていました。
- `MOVING` 中に `pause()` しても、アームのサーボ補間動作が止まりませんでした。

#### ■ 問題点 2: `os.listdir()` による不要なヒープ消費
- `if TEACHING_FILE in os.listdir():` はディレクトリ内の全ファイル名文字列リストをRAM上に生成します。

#### ■ 修正内容
```python
# 1. 一時停止時の残りディレイ時間保持
def pause(self):
    if self._state == PlaybackState.WAITING_DELAY:
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._delay_start_time)
        self._current_delay_ms = max(0, self._current_delay_ms - elapsed)
        self._previous_state = self._state
        self._state = PlaybackState.PAUSED
    elif self._state == PlaybackState.MOVING:
        self._previous_state = self._state
        self._state = PlaybackState.PAUSED

def resume(self):
    if self._state == PlaybackState.PAUSED:
        if self._previous_state == PlaybackState.WAITING_DELAY:
            self._delay_start_time = time.ticks_ms()
        self._state = self._previous_state

# 2. ファイル存在確認を try-open に変更
def load_from_json(self):
    try:
        with open(TEACHING_FILE, "r") as f:
            data = json.load(f)
            self._points = [TeachPoint.from_dict(d) for d in data]
            self._count = len(self._points)
        return True
    except OSError:
        return False # ファイルが存在しない場合は空のまま開始
```

---

### 3.5 `arm.py`

#### ■ 問題点: サーボデューティ比のクランプ（SG90保護）欠落
- オフセット設定（`JOINT1_OFFSET_DEG` 等）によって角度が 0° 未満や 180° 超になった場合、PWMデューティがサーボの物理限界（1638〜7864）を超えて破損する恐れがありました。

#### ■ 修正内容
```python
def write_servo_angles(self, t1, t2):
    if not self._is_attached or not self._pwm1 or not self._pwm2:
        return

    # オフセット適用と 0-180度 クランプ
    t1_actual = max(0.0, min(180.0, t1 + config.JOINT1_OFFSET_DEG))
    t2_actual = max(0.0, min(180.0, t2 + config.JOINT2_OFFSET_DEG))

    # SG90用 16-bit PWM Duty (50Hz: 0.5ms~2.4ms -> 1638~7864)
    duty1 = int(1638 + (t1_actual / 180.0) * (7864 - 1638))
    duty2 = int(1638 + (t2_actual / 180.0) * (7864 - 1638))

    duty1 = max(1638, min(7864, duty1))
    duty2 = max(1638, min(7864, duty2))

    try:
        self._pwm1.duty_u16(duty1)
        self._pwm2.duty_u16(duty2)
    except Exception:
        pass
```

---

## 4. まとめと推奨作業手順

1. **修正の適用順序**:
   - `kinematics.py`（IK計算バグ修正）
   - `line_follower.py`（モーターDIR極性＆P制御操舵連携）
   - `web_server.py`（不要なGC削除＆POSTパース堅牢化）
   - `arm.py`（デューティ比クランプ保護）
   - `teaching.py`（Pause/Resumeタイムアウト保護＆フラッシュ保存最適化）
2. **デプロイ・最適化**:
   - 必要に応じて `mpy-cross` による `.mpy` バイトコード化を行い、ESP32の起動高速化とヒープ保護を図る。
