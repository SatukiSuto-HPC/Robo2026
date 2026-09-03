# 🔍 デバッグレポート — MakerLine Arm MicroPython
**モデル**: Claude Sonnet 4.6 (Thinking)  
**解析日時**: 2026-09-02  
**方針**: ビルドなし・静的コード解析のみ。編集は行わず報告のみ。

---

## 📦 フラッシュメモリ使用量 (推定)

ESP32 MicroPython の一般的なフラッシュ構成:
- **合計フラッシュ**: 4MB (典型的な ESP32 モジュール)
- **MicroPython ファームウェア**: 約 1.5〜1.8MB
- **ユーザー領域 (VFS/SPIFFS)**: 約 1.5〜2.0MB

### ファイルサイズ一覧

| ファイル | サイズ | 備考 |
|---|---|---|
| `index.html` | **9,846 B** | ⚠️ 最大ファイル |
| `line_follower.py` | 9,447 B | |
| `arm.py` | 7,603 B | |
| `web_server.py` | 7,128 B | |
| `teaching.py` | 5,849 B | |
| `kinematics.py` | 3,910 B | |
| `config.py` | 1,979 B | |
| `main.py` | 1,788 B | |
| `boot.py` | 1,726 B | |
| **合計 (コード)** | **~49 KB** | |
| `teaching.json` (実行時生成) | 最大 ~4KB (32点) | ティーチングデータ |

> 合計 ~49KB + ファームウェア ~1.8MB なので、フラッシュ容量自体は問題なし。  
> ただし ESP32 の RAM (SRAM) は約320KB しかなく、`index.html` はストリーミング配信で正しく対応している。

---

## 🐛 バグ・問題点一覧

---

### 🔴 重大度: HIGH

---

#### Bug #1 — `line_follower.py:37` 存在しない `config.DIR_PIN` 参照

```python
# line_follower.py, 行37
self._left_dir = Pin(config.DIR_PIN if hasattr(config, 'DIR_PIN') else config.LEFT_DIR_PIN, Pin.OUT)
```

**問題**: `config.py` に `DIR_PIN` という定義は存在しない (`LEFT_DIR_PIN = 18` は存在する)。  
`hasattr(config, 'DIR_PIN')` は `False` を返すため実害は出ないが、意図不明なガードが残っている。  
他の3ピン (`_left_step`, `_right_step`, `_right_dir`) は直接 `config.LEFT_STEP_PIN` 等を参照しており、**この行だけコードスタイルが不統一**。  
将来 `config.py` に誰かが `DIR_PIN` を追加した場合、意図しない誤動作の原因になる。

---

#### Bug #2 — `execute_tracking_step()` が P 制御を全く使わない ← 最重要

```python
# line_follower.py, 行198-202
def execute_tracking_step(self):
    now_us = time.ticks_us()
    if time.ticks_diff(now_us, self._last_step_time_us) >= self._base_step_delay:
        self._last_step_time_us = now_us
        self.step_motors(True, True)  # ← 常に両モーター同速で前進！
```

**問題**: `execute_tracking_speed()` というP制御の速度計算メソッド（行188〜196）が存在するが、  
`execute_tracking_step()` では **一切呼ばれておらず、常に直進のみ**。  
ラインから外れても補正が効かない。`execute_tracking_speed()` は**デッドコード**になっている。

```python
# 使われていない行188-196
def execute_tracking_speed(self):
    correction = int(config.LINE_KP * self._sensor_error)
    left_delay = self._base_step_delay - correction
    right_delay = self._base_step_delay + correction
    left_delay = max(config.MIN_STEP_DELAY, min(config.MAX_STEP_DELAY, left_delay))
    right_delay = max(config.MIN_STEP_DELAY, min(config.MAX_STEP_DELAY, right_delay))
    return left_delay, right_delay
```

---

#### Bug #3 — `step_motors()` で左右モーターの STEP パルスが同時発生 → DRV8825 電流スパイクリスク

```python
# line_follower.py, 行228-232
self._left_step.value(1)
self._right_step.value(1)   # 左右同時にHIGH
time.sleep_us(10)
self._left_step.value(0)
self._right_step.value(0)
```

**問題**: 左右ドライバの電流が同時にスパイクし、電源電圧降下を起こす可能性がある。  
ESP32 の 3.3V ロジックラインが電源ノイズの影響を受けてリセットがかかるリスクがある。  
`execute_turn_left_step()` も同様の問題（行209-213）。

---

### 🟠 重大度: MEDIUM

---

#### Bug #4 — `kinematics.py:68` 原点 (0,0) で `atan2(0,0)` が不定になる可能性

```python
# kinematics.py, 行68
if r > max_reach or r < min_reach or r == 0.0:
    return JointAngles(0.0, 0.0, False)
```

**問題**: `min_reach = abs(l1 - l2) = abs(100 - 100) = 0.0` の場合、  
`r < min_reach` は `0.0 < 0.0 = False` となり、原点はすり抜けてしまう。  
`r == 0.0` チェックは意図は正しいが、`l1 == l2` 構成ではロジックが混乱する。

---

#### Bug #5 — 逆運動学の正規化範囲 (-180〜180) とサーボ制限 (0〜180) の不一致

```python
# kinematics.py, 行116-121
@staticmethod
def _normalize_angle_deg(deg):
    while deg > 180.0:
        deg -= 360.0
    while deg < -180.0:
        deg += 360.0
    return deg
```

**問題**: この正規化は `-180° ~ +180°` の範囲に収める。  
しかし `is_angles_valid()` は `JOINT1_MIN_DEG=0.0 ~ JOINT1_MAX_DEG=180.0` でチェック。  
逆運動学で得られた角度が**負の値**になった場合、正規化後も負のままで `False` になる。  
**物理的に到達可能な位置なのに到達不可と判定される**ケースが生じる可能性がある。

---

#### Bug #6 — `web_server.py:124` 不正JSON でレスポンスなしになる

```python
# web_server.py, 行124
req_json = json.loads(body) if body else {}
```

**問題**: 不正なJSON が来た場合は `json.loads()` が例外を投げ、  
`_handle_client()` 全体の `except Exception` でキャッチされる。  
**クライアントにはレスポンスが返らず、接続が突然切れるだけ**になる。  
同様に `/api/param` の行156も同じ問題。

---

#### Bug #7 — `web_server.py` がプライベート属性を直接参照 (カプセル化違反)

```python
# web_server.py, 行109, 111, 112
"servo": "ON" if self._arm._is_attached else "OFF",
"theta1": round(self._arm._current_theta1, 1),
"theta2": round(self._arm._current_theta2, 1),
```

**問題**: `arm.py` のプライベート属性を `web_server.py` が直接参照。  
将来 `arm.py` の内部実装を変更した場合、`web_server.py` が無言で壊れる。  
`arm.py` にはこれらのゲッターメソッドが存在しない。

---

### 🟡 重大度: LOW / 設計上の懸念

---

#### Bug #8 — `teaching.py:87` 存在しないメソッドの `hasattr` チェック

```python
# teaching.py, 行87-88
t1 = self._arm.getCurrentTheta1() if hasattr(self._arm, 'getCurrentTheta1') else self._arm._current_theta1
t2 = self._arm.getCurrentTheta2() if hasattr(self._arm, 'getCurrentTheta2') else self._arm._current_theta2
```

**問題**: `arm.py` に `getCurrentTheta1()` / `getCurrentTheta2()` は**定義されていない**。  
常に `else` 側のプライベート属性アクセスにフォールバックする。未使用の `hasattr` チェックが残っている。

---

#### Bug #9 — `arm.py:143` `set_joint_angles_instant()` が attach を保証しない

```python
# arm.py, 行142-144
if max_dist < 0.1:
    self.set_joint_angles_instant(theta1_deg, theta2_deg)
    return True
```

**問題**: `set_joint_angles_instant()` が `public` メソッドとして外部から直接呼ばれた場合、  
サーボがアタッチされていなくても `write_servo_angles()` が呼ばれる。  
（ただし `_is_attached` チェックで無害にスキップされるため動作上の被害はない）

---

#### Bug #10 — `main.py:32` コメントのステップ番号が「4」を飛ばして「5」にジャンプ

```python
# main.py, 行32
# 5. Main Cooperative Loop   ← "4." が存在しない
```

**問題**: `1.`〜`3.` の後、`5.` に飛んでいる。4番目のステップが欠落またはコメント漏れ。  
動作には影響しないが、コードの可読性・保守性に影響する。

---

#### Bug #11 — `web_server.py` の `start()` メソッドが `begin()` と重複

```python
# web_server.py, 行37-39
def start(self):
    if not self._server_s:
        self.begin()
```

**問題**: `main.py` は `web_server.begin()` を呼んでおり、`start()` は一切使われていない。  
`begin()` と `start()` の2種類の初期化インターフェースが重複している。

---

#### Bug #12 — `index.html` に `points`（ティーチングポイント数）の表示UIがない

**問題**: `/api/status` のJSONレスポンスには `"points"` フィールドが含まれるが、  
`index.html` の `pollStatus()` では `d.points` を**受け取っているが画面表示していない**。  
ティーチングポイント数がUIに反映されない。

---

## 📊 フラッシュ・RAM 使用上の懸念まとめ

| 項目 | 状況 |
|---|---|
| フラッシュ容量 (総コード ~49KB) | 問題なし ✅ |
| `index.html` (9.8KB) ストリーム配信 | 正しい設計 ✅ |
| `bytearray(512)` 再利用バッファ | 初期化時1回のみ確保 — 良い設計 ✅ |
| `teaching.json` 最大サイズ (~1.4KB) | 問題なし ✅ |
| `json.loads(body)` の一時RAM展開 | 通常問題ないが大きなPOSTは注意 ⚠️ |
| `gc.collect()` 毎リクエスト後呼び出し | 良い設計 ✅ |
| `__pycache__` フォルダのアップロード | ESP32書き込み時に**除外必須** ⚠️ |

> **`__pycache__` フォルダをESP32にアップロードしてしまうと、無駄なフラッシュ消費になる。**  
> `ampy` や `rshell` での書き込み時に除外すること。

---

## 🗂 優先度サマリー

| 優先度 | Bug# | ファイル | 概要 |
|---|---|---|---|
| 🔴 HIGH | #2 | `line_follower.py` | P制御がデッドコード化 — ライントレース機能しない |
| 🔴 HIGH | #1 | `line_follower.py` | `DIR_PIN` 不整合参照（現状無害だが危険） |
| 🔴 HIGH | #3 | `line_follower.py` | 両モーター同時パルス — 電源ノイズリスク |
| 🟠 MEDIUM | #4 | `kinematics.py` | 原点で `atan2(0,0)` 不定値リスク |
| 🟠 MEDIUM | #5 | `kinematics.py` | 正規化範囲 vs. サーボ制限の不一致 |
| 🟠 MEDIUM | #6 | `web_server.py` | 不正JSONでレスポンスなし |
| 🟠 MEDIUM | #7 | `web_server.py` | プライベート属性への直接アクセス |
| 🟡 LOW | #8 | `teaching.py` | 存在しないメソッドの `hasattr` チェック |
| 🟡 LOW | #9 | `arm.py` | `set_joint_angles_instant` の attach 保証なし |
| 🟡 LOW | #10 | `main.py` | コメント番号の欠落（4番が飛んでいる） |
| 🟡 LOW | #11 | `web_server.py` | `begin()`/`start()` の重複 |
| 🟡 LOW | #12 | `index.html` | `points` データがUIに表示されない |
