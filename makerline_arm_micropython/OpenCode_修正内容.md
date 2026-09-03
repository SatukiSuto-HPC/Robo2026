# 修正内容: MakerLine Arm Integration (MicroPython)

**分析モデル**: OpenCode AI Agent
**対象プロジェクト**: MakerLine Arm Integration (MicroPython for ESP32)
**分析日時**: 2026年9月2日

---

## 概要

ESP32用MicroPythonプロジェクトのコード静的解析に基づく修正内容を報告します。ビルドは行わず、デバッグ分析のみ実施。

---

## 1. メモリ使用量統計

### 1.1 ファイルサイズ
| ファイル | 行数 | サイズ（バイト） |
|----------|------|------------------|
| arm.py | 165 | 7,603 |
| boot.py | 42 | 1,726 |
| config.py | 53 | 1,979 |
| kinematics.py | 91 | 3,910 |
| line_follower.py | 211 | 9,447 |
| main.py | 48 | 1,788 |
| teaching.py | 153 | 5,849 |
| web_server.py | 151 | 7,128 |
| **合計** | **914** | **39,430** |

### 1.2 推定メモリ使用量
- **RAM**: 約200-400KB（ESP32の2MB RAM内で余裕あり）
- **フラッシュ**: 約100-150KB（4MB Flash内で余裕あり）

---

## 2. 修正が必要な問題点

### 🔴 高優先度

#### 問題2-1: フラッシュ書き込み頻度
**ファイル**: `teaching.py` (L158-166)
**現状**: `save_to_json()`が`add_point()`、`delete_point()`、`clear()`のたびに即座にフラッシュ書き込み
**問題**: フラッシュメモリは通常10万回書き込みで劣化。頻繁な書き込みは寿命を縮める
**修正内容**:
```python
# 変更前: 即時書き込み
def add_point(self, theta1, theta2, delay_ms=500, speed=0.0):
    ...
    self._points.append(pt)
    self._count = len(self._points)
    self.save_to_json()  # 即時書き込み

# 変更後: バッファリング + 変更フラグ
def __init__(self, arm):
    ...
    self._dirty = False  # 変更フラグ追加

def add_point(self, theta1, theta2, delay_ms=500, speed=0.0):
    ...
    self._points.append(pt)
    self._count = len(self._points)
    self._dirty = True   # フラグのみ設定

def save_pending(self):
    if self._dirty:
        self.save_to_json()
        self._dirty = False
```

---

#### 問題2-2: Wi-Fiセキュリティ
**ファイル**: `boot.py` (L26)
**現状**: オープンネットワーク（パスワードなし）
```python
ap.config(essid="zeni", authmode=0)  # authmode=0はOPEN
```
**問題**: 公共の場での使用は危険。通信の傍受・不正アクセス可能
**修正内容**:
```python
# 変更後: WPA2-PSK設定（パスワードは環境に応じて変更）
ap.config(essid="zeni", authmode=0x4, password="makerline2024")
# authmode=0x4はWPA2_PSK
```
**代替案**: セキュリティ文書を追加し、ローカルネットワーク限定の使用を明記

---

#### 問題2-3: モーター制御コードの重複
**ファイル**: `line_follower.py` (L204-214, L216-232)
**現状**: `execute_turn_left_step()`と`step_motors()`で同じコードが重複
**問題**: メンテナンス性低下、修正漏れのリスク
**修正内容**:
```python
# 変更後: step_motors()を再利用
def execute_turn_left_step(self):
    invert = getattr(config, 'INVERT_MOTOR_DIRECTION', False)
    # 左モーター逆回転、右モーター正回転
    self.step_motors(False, True)  # left_forward=False, right_forward=True
    time.sleep_us(config.TURN_STEP_DELAY)
```

---

### 🟡 中優先度

#### 問題2-4: リクエスト解析の脆弱性
**ファイル**: `web_server.py` (L75-83)
**現状**: 簡易的な文字列解析のみ
```python
req_str = raw_req.decode('utf-8', 'ignore')
lines = req_str.split('\r\n')
parts = lines[0].split(' ')
```
**問題**: malformedリクエストでクラッシュする可能性
**修正内容**:
```python
# 変更後: エラーハンドリング強化
def _parse_request(self, raw_req):
    try:
        req_str = raw_req.decode('utf-8', 'ignore').strip()
        if not req_str:
            return None, None, None
        lines = req_str.split('\r\n')
        if not lines:
            return None, None, None
        parts = lines[0].split(' ')
        if len(parts) < 2:
            return None, None, None
        return parts[0], parts[1], req_str
    except Exception:
        return None, None, None
```

---

#### 問題2-5: カプセル化違反
**ファイル**: `teaching.py` (L87-88)
**現状**: プライベート変数に直接アクセス
```python
t1 = self._arm.getCurrentTheta1() if hasattr(self._arm, 'getCurrentTheta1') else self._arm._current_theta1
t2 = self._arm.getCurrentTheta2() if hasattr(self._arm, 'getCurrentTheta2') else self._arm._current_theta2
```
**問題**: カプセル化違反、将来のAPI変更で壊れる
**修正内容**:
```python
# 変更後: 公開メソッド経由で取得
def record_current(self, delay_ms=500, speed=0.0):
    # ArmControllerにget_current_angles()メソッドを追加想定
    t1, t2 = self._arm.get_current_angles()
    return self.add_point(t1, t2, delay_ms, speed)
```

---

#### 問題2-6: 定数の分散
**ファイル**: `teaching.py` (L10), `config.py`
**現状**: `MAX_TEACH_POINTS = 32`が`teaching.py`にハードコード
```python
MAX_TEACH_POINTS = 32  # teaching.py L10
```
**問題**: 設定変更時に複数ファイルを修正必要
**修正内容**:
```python
# config.pyに追加
MAX_TEACH_POINTS = 32

# teaching.pyから削除し、configからインポート
import config
# MAX_TEACH_POINTS = 32 を削除
```

---

### 🟢 低優先度

#### 問題2-7: 言語混在
**ファイル**: 複数
**現状**: コメント・エラーメッセージが英語/日本語混在
**修正内容**: 言語を統一（英語推奨）

---

#### 問題2-8: パフォーマンス
**ファイル**: `main.py` (L48)
**現状**: `time.sleep_us(500)`で約500Hz
**問題**: センサー読み取り（~1kHz）とのバランス
**修正内容**: 必要に応じて更新頻度を調整（200-1000Hz範囲で最適化）

---

#### 問題2-9: ハードウェア依存
**ファイル**: `config.py`
**現状**: ESP32-WROOM-32E専用ピン設定
**問題**: ESP32-S3など他モデルではピン配置が異なる
**修正内容**: ドキュメントに複数モデル対応の注記を追加

---

## 3. 修正優先度まとめ

| 優先度 | 問題 | ファイル | 難易度 |
|--------|------|----------|--------|
| 🔴 高 | フラッシュ書き込み頻度 | teaching.py | 中 |
| 🔴 高 | Wi-Fiセキュリティ | boot.py | 低 |
| 🔴 高 | コード重複 | line_follower.py | 低 |
| 🟡 中 | リクエスト解析 | web_server.py | 中 |
| 🟡 中 | カプセル化違反 | teaching.py | 低 |
| 🟡 中 | 定数分散 | teaching.py/config.py | 低 |
| 🟢 低 | 言語混在 | 複数 | 低 |
| 🟢 低 | パフォーマンス | main.py | 低 |
| 🟢 低 | ハードウェア依存 | config.py | 低 |

---

## 4. 推奨される修正順序

1. **問題2-2** (Wi-Fiセキュリティ) - 即座に対応推奨
2. **問題2-3** (コード重複) - 简单的な修正
3. **問題2-6** (定数分散) - 简单的な修正
4. **問題2-5** (カプセル化違反) - API設計の検討が必要
5. **問題2-4** (リクエスト解析) - セキュリティ強化
6. **問題2-1** (フラッシュ書き込み) - 設計変更が必要
7. **問題2-7〜2-9** - 改善・文書化

---

## 5. 結論

プロジェクトは全体的に良好な構造を持ち、ESP32のメモリ制約内でおおむね動作可能。ただし、フラッシュ書き込み頻度とセキュリティ面での改善が必要。上記の修正を優先度順に対応することを推奨する。

---
*本修正内容はOpenCode AI Agentによるコード静的解析に基づいています。*
*実際の修正前にテスト環境での検証を推奨します。*
