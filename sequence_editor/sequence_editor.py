import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import threading
import datetime
import os

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# ── テーマカラー (Catppuccin Mocha) ──────────────────────────────────────────
BG_COLOR     = "#1e1e2e"
FG_COLOR     = "#cdd6f4"
ACCENT_COLOR = "#89b4fa"
FRAME_BG     = "#313244"
ENTRY_BG     = "#45475a"
ENTRY_FG     = "#cdd6f4"
SELECT_BG    = "#585b70"
GREEN_COLOR  = "#a6e3a1"

TASK_COLORS = {
    "LINE_TRACE": "#89dceb",
    "ARM_MOVE":   "#cba6f7",
    "DRIVE":      "#a6e3a1",
    "WAIT":       "#f9e2af",
    "WAIT_QR":    "#eba0ac",
    "STOP":       "#f38ba8",
    "GOAL":       "#fab387",
}

DEFAULT_DATA = {
    "version": 2,
    "start_trigger": {"type": "QR_ANY", "qr_data": ""},
    "tasks": [
        {"name": "荷物置き場へ移動", "type": "LINE_TRACE", "trigger": "QR",   "qr_data": "pickup_zone"},
        {"name": "アーム上昇・開放", "type": "ARM_MOVE",   "arm_s1": 45,  "arm_s2": 135, "wait_ms": 1000},
        {"name": "前進（2秒）",      "type": "DRIVE",      "direction": "FORWARD", "duration_ms": 2000, "speed": 1200},
        {"name": "荷物を把持",       "type": "ARM_MOVE",   "arm_s1": 60,  "arm_s2": 175, "wait_ms": 1000},
        {"name": "目的地へ移動",     "type": "LINE_TRACE", "trigger": "QR",   "qr_data": "dropoff_zone"},
        {"name": "荷物を放す",       "type": "ARM_MOVE",   "arm_s1": 45,  "arm_s2": 135, "wait_ms": 1000},
        {"name": "GOAL",             "type": "GOAL"},
    ],
    "line_params": {
        "BASE_STEP_DELAY": 1200,
        "MIN_STEP_DELAY":  400,
        "MAX_STEP_DELAY":  4000,
        "LINE_KP":         250.0,
        "ALL_LINE_DEBOUNCE_MS": 80,
    }
}


class SequenceEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Robo2026 シーケンスエディター v2")
        self.geometry("1100x860")
        self.configure(bg=BG_COLOR)

        self.current_data  = json.loads(json.dumps(DEFAULT_DATA))
        self.selected_index = None
        self.serial_port   = None
        self.running_serial = False

        self._setup_styles()
        self._build_ui()
        self._populate_task_list()
        self._populate_params()
        self._load_start_trigger()

        if not HAS_SERIAL:
            messagebox.showwarning("警告",
                "pyserialが見つかりません。シリアル機能は無効です。\npip install pyserial")

    # ── スタイル ─────────────────────────────────────────────────────────────
    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".",                background=BG_COLOR,  foreground=FG_COLOR, font=("Helvetica", 10))
        s.configure("TFrame",           background=BG_COLOR)
        s.configure("TLabelframe",      background=BG_COLOR,  foreground=ACCENT_COLOR)
        s.configure("TLabelframe.Label",background=BG_COLOR,  foreground=ACCENT_COLOR, font=("Helvetica", 10, "bold"))
        s.configure("TLabel",           background=BG_COLOR,  foreground=FG_COLOR)
        s.configure("TButton",          background=FRAME_BG,  foreground=FG_COLOR, borderwidth=1)
        s.map("TButton",                background=[("active", SELECT_BG)])
        s.configure("Accent.TButton",   background=ACCENT_COLOR, foreground=BG_COLOR, font=("Helvetica", 10, "bold"))
        s.map("Accent.TButton",         background=[("active", "#b4befe")])
        s.configure("Treeview",         background=ENTRY_BG, fieldbackground=ENTRY_BG, foreground=FG_COLOR, borderwidth=0, rowheight=24)
        s.map("Treeview",               background=[("selected", ACCENT_COLOR)], foreground=[("selected", BG_COLOR)])
        s.configure("TEntry",           fieldbackground=ENTRY_BG, foreground=ENTRY_FG)
        s.configure("TCombobox",        fieldbackground=ENTRY_BG, foreground=ENTRY_FG)
        s.configure("TRadiobutton",     background=BG_COLOR,  foreground=FG_COLOR)
        s.configure("TScale",           background=BG_COLOR,  troughcolor=FRAME_BG)

    # ── UI構築 ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ヘッダー
        hdr = ttk.Frame(main)
        hdr.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(hdr, text="Robo2026 シーケンスエディター v2",
                  font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        ttk.Button(hdr, text="コード生成", style="Accent.TButton",
                   command=self.generate_code).pack(side=tk.RIGHT, padx=5)
        ttk.Button(hdr, text="保存",   command=self.save_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(hdr, text="開く",   command=self.open_file).pack(side=tk.RIGHT, padx=5)

        # ── 開始条件 ──
        sf = ttk.Labelframe(main, text="▶ シーケンス開始条件")
        sf.pack(fill=tk.X, pady=(0, 5))
        sfi = ttk.Frame(sf)
        sfi.pack(fill=tk.X, padx=10, pady=6)

        self.var_start_type = tk.StringVar(value="QR_ANY")
        ttk.Radiobutton(sfi, text="即時開始（起動後すぐ）",
                        variable=self.var_start_type, value="IMMEDIATE",
                        command=self._on_start_type_change).grid(row=0, column=0, sticky="w", padx=8)
        ttk.Radiobutton(sfi, text="QR受信で開始（内容不問）",
                        variable=self.var_start_type, value="QR_ANY",
                        command=self._on_start_type_change).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Radiobutton(sfi, text="QR受信で開始（内容指定）:",
                        variable=self.var_start_type, value="QR_DATA",
                        command=self._on_start_type_change).grid(row=0, column=2, sticky="w", padx=8)
        self.var_start_qr = tk.StringVar()
        self.entry_start_qr = tk.Entry(sfi, textvariable=self.var_start_qr,
                                        bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=FG_COLOR, width=22,
                                        state="disabled")
        self.entry_start_qr.grid(row=0, column=3, sticky="w", padx=5)
        ttk.Label(sfi, text="（QRコードに書かれた文字列）", foreground="gray",
                  font=("Helvetica", 8)).grid(row=0, column=4, sticky="w", padx=2)

        # ── メインペイン ──
        paned = tk.PanedWindow(main, orient=tk.HORIZONTAL, bg=BG_COLOR, sashwidth=5)
        paned.pack(fill=tk.BOTH, expand=True, pady=5)

        # 左: タスクリスト
        lf = ttk.Labelframe(paned, text="タスクリスト")
        paned.add(lf, minsize=330)

        self.tree = ttk.Treeview(lf, columns=("no","name","type"), show="headings", selectmode="browse")
        self.tree.heading("no",   text="#")
        self.tree.heading("name", text="タスク名")
        self.tree.heading("type", text="種別")
        self.tree.column("no",   width=28, stretch=False)
        self.tree.column("name", width=165)
        self.tree.column("type", width=105)
        for tt, c in TASK_COLORS.items():
            self.tree.tag_configure(tt, foreground=c)
        sc = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sc.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        sc.pack(side=tk.LEFT, fill=tk.Y, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_task_select)

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_row, text="↑ 上へ",  command=self.move_up).pack(side=tk.LEFT,  padx=2)
        ttk.Button(btn_row, text="↓ 下へ",  command=self.move_down).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="+ 追加",  command=self.add_task).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_row, text="削除",    command=self.delete_task).pack(side=tk.RIGHT, padx=2)

        # 右: プロパティ
        rf = ttk.Frame(paned)
        paned.add(rf, minsize=430)
        self.prop_lf = ttk.Labelframe(rf, text="タスクプロパティ")
        self.prop_lf.pack(fill=tk.BOTH, expand=True, padx=5)

        cf = ttk.Frame(self.prop_lf)
        cf.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(cf, text="タスク名:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        self.var_task_name = tk.StringVar()
        self.var_task_name.trace_add("write", self.on_property_change)
        tk.Entry(cf, textvariable=self.var_task_name,
                 bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=FG_COLOR, width=30
                 ).grid(row=0, column=1, columnspan=3, sticky="w", pady=4)

        ttk.Label(cf, text="種別:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.var_task_type = tk.StringVar()
        cb = ttk.Combobox(cf, textvariable=self.var_task_type, width=14, state='readonly', values=['LINE_TRACE','ARM_MOVE','DRIVE','WAIT','WAIT_QR','STOP','GOAL'])
        cb.grid(row=1, column=1, sticky='w', pady=4)
        cb.bind("<<ComboboxSelected>>", self.on_type_change)

        self.dyn = ttk.Frame(self.prop_lf)
        self.dyn.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ── 下部 ──
        bot = ttk.Frame(main)
        bot.pack(fill=tk.X, pady=5)

        pf = ttk.Labelframe(bot, text="ライントレースパラメータ (config.py)")
        pf.pack(fill=tk.X, pady=(0,5))
        self.param_vars = {}
        pg = ttk.Frame(pf)
        pg.pack(padx=10, pady=5)
        for label, key, r, c in [
            ("BASE_STEP_DELAY(μs):", "BASE_STEP_DELAY",      0, 0),
            ("MIN_STEP_DELAY(μs):",  "MIN_STEP_DELAY",       0, 2),
            ("MAX_STEP_DELAY(μs):",  "MAX_STEP_DELAY",       0, 4),
            ("LINE_KP:",             "LINE_KP",              1, 0),
            ("ALL_LINE_DEBOUNCE(ms):", "ALL_LINE_DEBOUNCE_MS", 1, 2),
        ]:
            ttk.Label(pg, text=label).grid(row=r, column=c, sticky="e", padx=5, pady=4)
            v = tk.StringVar()
            self.param_vars[key] = v
            tk.Entry(pg, textvariable=v, bg=ENTRY_BG, fg=ENTRY_FG,
                     insertbackground=FG_COLOR, width=10).grid(row=r, column=c+1, sticky="w", padx=5)
        ttk.Button(pf, text="パラメータ保存", command=self.save_params).pack(side=tk.RIGHT, padx=10, pady=5)

        serf = ttk.Labelframe(bot, text="シリアル通信（Arduino直接送信テスト）")
        serf.pack(fill=tk.X)
        sr1 = ttk.Frame(serf); sr1.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(sr1, text="ポート:").pack(side=tk.LEFT)
        self.var_port = tk.StringVar()
        self.port_cb = ttk.Combobox(sr1, textvariable=self.var_port, width=10)
        self.port_cb.pack(side=tk.LEFT, padx=5)
        self.update_ports()
        ttk.Label(sr1, text="Baud:").pack(side=tk.LEFT)
        self.var_baud = tk.StringVar(value="9600")
        ttk.Combobox(sr1, textvariable=self.var_baud, values=["9600","115200"], width=8).pack(side=tk.LEFT, padx=5)
        self.btn_conn = ttk.Button(sr1, text="接続", command=self.toggle_serial)
        self.btn_conn.pack(side=tk.LEFT, padx=5)
        self.lbl_conn = ttk.Label(sr1, text="● 未接続", foreground="gray")
        self.lbl_conn.pack(side=tk.LEFT, padx=10)

        sr2 = ttk.Frame(serf); sr2.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(sr2, text="コマンド:").pack(side=tk.LEFT)
        self.var_cmd = tk.StringVar()
        tk.Entry(sr2, textvariable=self.var_cmd, bg=ENTRY_BG, fg=ENTRY_FG,
                 insertbackground=FG_COLOR, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(sr2, text="送信",   command=self.send_command).pack(side=tk.LEFT, padx=3)
        ttk.Button(sr2, text="PING",   command=lambda:(self.var_cmd.set("PING"),   self.send_command())).pack(side=tk.LEFT, padx=3)
        ttk.Button(sr2, text="STATUS", command=lambda:(self.var_cmd.set("STATUS"), self.send_command())).pack(side=tk.LEFT, padx=3)
        ttk.Button(sr2, text="FREE",   command=lambda:(self.var_cmd.set("FREE"),   self.send_command())).pack(side=tk.LEFT, padx=3)

        sr3 = ttk.Frame(serf); sr3.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(sr3, text="ログ:").pack(side=tk.LEFT)
        self.log_text = tk.Text(sr3, height=3, bg=ENTRY_BG, fg=ENTRY_FG, font=("Consolas",9))
        self.log_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    # ── 開始条件 ──────────────────────────────────────────────────────────────
    def _on_start_type_change(self):
        t = self.var_start_type.get()
        self.current_data["start_trigger"]["type"] = t
        self.entry_start_qr.config(state="normal" if t == "QR_DATA" else "disabled")

    def _load_start_trigger(self):
        st = self.current_data.get("start_trigger", {"type": "QR_ANY", "qr_data": ""})
        self.var_start_type.set(st.get("type", "QR_ANY"))
        self.var_start_qr.set(st.get("qr_data", ""))
        self._on_start_type_change()
        self.var_start_qr.trace_add("write", self._on_start_qr_change)

    def _on_start_qr_change(self, *a):
        self.current_data["start_trigger"]["qr_data"] = self.var_start_qr.get()

    # ── ポート ────────────────────────────────────────────────────────────────
    def update_ports(self):
        if HAS_SERIAL:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.port_cb["values"] = ports
            if ports:
                self.port_cb.set(ports[0])

    # ── タスクリスト ──────────────────────────────────────────────────────────
    def _populate_task_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, t in enumerate(self.current_data["tasks"]):
            tt = t.get("type", "")
            tag = tt if tt in TASK_COLORS else ""
            self.tree.insert("", "end", iid=str(i),
                             values=(i+1, t.get("name",""), tt), tags=(tag,))

    def _populate_params(self):
        for k, v in self.current_data.get("line_params", {}).items():
            if k in self.param_vars:
                self.param_vars[k].set(str(v))

    def save_params(self, silent=False):
        for k, var in self.param_vars.items():
            try:
                val = var.get()
                self.current_data["line_params"][k] = float(val) if "." in val else int(val)
            except ValueError:
                pass
        if not silent:
            messagebox.showinfo("保存", "パラメータを更新しました。")

    # ── タスク選択/編集 ───────────────────────────────────────────────────────
    def on_task_select(self, event):
        sel = self.tree.selection()
        if not sel:
            self.selected_index = None
            self._clear_dyn()
            return
        idx = int(sel[0])
        self.selected_index = idx
        task = self.current_data["tasks"][idx]
        info = self.var_task_name.trace_info()
        if info:
            self.var_task_name.trace_vdelete("w", info[0][1])
        self.var_task_name.set(task.get("name", ""))
        self.var_task_name.trace_add("write", self.on_property_change)
        self.var_task_type.set(task.get("type", ""))
        self._build_dyn(task)

    def on_type_change(self, event):
        if self.selected_index is None:
            return
        nt = self.var_task_type.get()
        task = self.current_data["tasks"][self.selected_index]
        task["type"] = nt
        defaults = {
            "LINE_TRACE": {"trigger": "QR", "qr_data": ""},
            "ARM_MOVE":   {"arm_s1": 90, "arm_s2": 90, "wait_ms": 1000},
            'DRIVE':      {'direction': 'FORWARD', 'duration_ms': 2000, 'speed': 1200},
            'WAIT':       {'wait_ms': 1000},
            'WAIT_QR':    {'qr_data': ''},
        }
        for k, v in defaults.get(nt, {}).items():
            task.setdefault(k, v)
        self._populate_task_list()
        self.tree.selection_set(str(self.selected_index))
        self._build_dyn(task)
        self.on_property_change()

    def on_property_change(self, *args):
        if self.selected_index is None:
            return
        sel = self.tree.selection()
        if not sel:
            return
        task = self.current_data["tasks"][self.selected_index]
        task["name"] = self.var_task_name.get()
        tt = task.get("type", "")
        tag = tt if tt in TASK_COLORS else ""
        self.tree.item(sel[0], values=(self.selected_index+1, task["name"], tt), tags=(tag,))

    def _clear_dyn(self):
        for w in self.dyn.winfo_children():
            w.destroy()

    def _build_dyn(self, task):
        self._clear_dyn()
        stype = task.get("type", "")
        color = TASK_COLORS.get(stype, FG_COLOR)
        ttk.Label(self.dyn, text=f"─── {stype} 設定 ───",
                  foreground=color, font=("Helvetica", 10, "bold")).pack(pady=(4, 8))
        {
            "LINE_TRACE": self._dyn_line_trace,
            "ARM_MOVE":   self._dyn_arm_move,
            'DRIVE':      self._dyn_drive,
            'WAIT':       self._dyn_wait,
            'WAIT_QR':    self._dyn_wait_qr,
        }.get(stype, lambda t: ttk.Label(self.dyn, text="追加設定なし",
                                          foreground="gray").pack(pady=20))(task)

    def _dyn_line_trace(self, task):
        f = ttk.Frame(self.dyn); f.pack(fill=tk.X, padx=5)
        ttk.Label(f, text="完了条件:").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        var_tr = tk.StringVar(value=task.get("trigger", "QR"))
        ttk.Combobox(f, textvariable=var_tr, values=["QR","TIME","ALL_LINE"],
                     state="readonly", width=12).grid(row=0, column=1, sticky="w", pady=5)
        dep = ttk.Frame(self.dyn); dep.pack(fill=tk.X, padx=25)
        def refresh(*a):
            task["trigger"] = var_tr.get()
            for w in dep.winfo_children(): w.destroy()
            t = var_tr.get()
            if t == "QR":
                ttk.Label(dep, text="QRデータ（空=任意QR）:").grid(row=0, column=0, sticky="e", padx=5, pady=3)
                vq = tk.StringVar(value=task.get("qr_data",""))
                def on_q(*a): task["qr_data"] = vq.get()
                vq.trace_add("write", on_q)
                tk.Entry(dep, textvariable=vq, bg=ENTRY_BG, fg=ENTRY_FG,
                         insertbackground=FG_COLOR, width=22).grid(row=0, column=1, sticky="w")
                ttk.Label(dep, text="※ 空欄 = どんなQRでも反応", foreground="gray",
                          font=("Helvetica", 8)).grid(row=1, column=1, sticky="w")
            elif t == "TIME":
                ttk.Label(dep, text="走行時間(ms):").grid(row=0, column=0, sticky="e", padx=5, pady=3)
                vt = tk.StringVar(value=str(task.get("trigger_value", 2000)))
                def on_t(*a):
                    try: task["trigger_value"] = int(vt.get())
                    except: pass
                vt.trace_add("write", on_t)
                tk.Entry(dep, textvariable=vt, bg=ENTRY_BG, fg=ENTRY_FG,
                         insertbackground=FG_COLOR, width=10).grid(row=0, column=1, sticky="w")
            elif t == "ALL_LINE":
                ttk.Label(dep, text="全センサーがライン検知した時に停止・次へ",
                          foreground=TASK_COLORS["WAIT"]).pack(pady=5)
        var_tr.trace_add("write", refresh)
        refresh()

    def _dyn_arm_move(self, task):
        f = ttk.Frame(self.dyn); f.pack(fill=tk.X, padx=5)
        f.columnconfigure(2, weight=1)
        for row, key, label in [(0,"arm_s1","S1 上下角度:"),(1,"arm_s2","S2 グリッパー:")]:
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="e", pady=6, padx=5)
            var = tk.IntVar(value=task.get(key, 90))
            lbl = ttk.Label(f, text=f"{var.get():>3}°", width=5, foreground=ACCENT_COLOR)
            lbl.grid(row=row, column=1)
            def make_cb(v, l, k):
                def cb(val):
                    iv = int(float(val)); v.set(iv); l.config(text=f"{iv:>3}°"); task[k] = iv
                return cb
            ttk.Scale(f, from_=0, to=180, variable=var,
                      command=make_cb(var, lbl, key)).grid(row=row, column=2, sticky="we", padx=5)
        ttk.Label(f, text="アーム動作待機(ms):").grid(row=2, column=0, sticky="e", pady=6, padx=5)
        vw = tk.StringVar(value=str(task.get("wait_ms", 1000)))
        def on_w(*a):
            try: task["wait_ms"] = int(vw.get())
            except: pass
        vw.trace_add("write", on_w)
        tk.Entry(f, textvariable=vw, bg=ENTRY_BG, fg=ENTRY_FG,
                 insertbackground=FG_COLOR, width=10).grid(row=2, column=1, columnspan=2, sticky="w", padx=5)
        def send_test():
            self.var_cmd.set(f"POS:{task.get('arm_s1',90)}:{task.get('arm_s2',90)}")
            self.send_command()
        ttk.Button(f, text="▶ この角度をArduinoへ送信テスト",
                   command=send_test).grid(row=3, column=0, columnspan=3, pady=8)

    def _dyn_drive(self, task):
        f = ttk.Frame(self.dyn); f.pack(fill=tk.X, padx=5)
        ttk.Label(f, text="走行方向:").grid(row=0, column=0, sticky="e", pady=6, padx=5)
        vd = tk.StringVar(value=task.get("direction", "FORWARD"))
        ttk.Combobox(f, textvariable=vd, width=14, state="readonly",
                     values=["FORWARD","BACKWARD","TURN_LEFT","TURN_RIGHT"]
                     ).grid(row=0, column=1, sticky="w", pady=6)
        hints = {
            "FORWARD":    "→ 両輪前進（ラインセンサー無視）",
            "BACKWARD":   "← 両輪後退",
            "TURN_LEFT":  "↺ 左ピボットターン（左後退・右前進）",
            "TURN_RIGHT": "↻ 右ピボットターン（左前進・右後退）",
        }
        lbl_h = ttk.Label(f, text=hints.get(vd.get(), ""), foreground="gray", font=("Helvetica", 8))
        lbl_h.grid(row=0, column=2, sticky="w", padx=10)
        def on_d(*a):
            task["direction"] = vd.get()
            lbl_h.config(text=hints.get(vd.get(), ""))
        vd.trace_add("write", on_d)
        ttk.Label(f, text="走行時間(ms):").grid(row=1, column=0, sticky="e", pady=6, padx=5)
        vdur = tk.StringVar(value=str(task.get("duration_ms", 2000)))
        def on_dur(*a):
            try: task["duration_ms"] = int(vdur.get())
            except: pass
        vdur.trace_add("write", on_dur)
        tk.Entry(f, textvariable=vdur, bg=ENTRY_BG, fg=ENTRY_FG,
                 insertbackground=FG_COLOR, width=10).grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="ms", foreground="gray").grid(row=1, column=2, sticky="w", padx=5)
        ttk.Label(f, text="速度(step_delay μs):").grid(row=2, column=0, sticky="e", pady=6, padx=5)
        vspd = tk.StringVar(value=str(task.get("speed", 1200)))
        def on_spd(*a):
            try: task["speed"] = int(vspd.get())
            except: pass
        vspd.trace_add("write", on_spd)
        tk.Entry(f, textvariable=vspd, bg=ENTRY_BG, fg=ENTRY_FG,
                 insertbackground=FG_COLOR, width=10).grid(row=2, column=1, sticky="w")
        ttk.Label(f, text="μs（小さい=速い / 最小400推奨）", foreground="gray",
                  font=("Helvetica", 8)).grid(row=2, column=2, sticky="w", padx=5)

    def _dyn_wait(self, task):
        f = ttk.Frame(self.dyn); f.pack(fill=tk.X, padx=5)
        ttk.Label(f, text="待機時間(ms):").grid(row=0, column=0, sticky="e", pady=6, padx=5)
        vw = tk.StringVar(value=str(task.get("wait_ms", 1000)))
        def on_w(*a):
            try: task["wait_ms"] = int(vw.get())
            except: pass
        vw.trace_add("write", on_w)
        tk.Entry(f, textvariable=vw, bg=ENTRY_BG, fg=ENTRY_FG,
                 insertbackground=FG_COLOR, width=10).grid(row=0, column=1, sticky="w")

    def _dyn_wait_qr(self, task):
        f = ttk.Frame(self.dyn); f.pack(fill=tk.X, padx=5)
        ttk.Label(f, text='QRデータ（空=任意QR）:').grid(row=0, column=0, sticky='e', pady=6, padx=5)
        vq = tk.StringVar(value=task.get('qr_data', ''))
        def on_q(*a): task['qr_data'] = vq.get()
        vq.trace_add('write', on_q)
        tk.Entry(f, textvariable=vq, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=FG_COLOR, width=22).grid(row=0, column=1, sticky='w')
        ttk.Label(f, text='※ この文字列のQRを認識するまでその場で待機', foreground='gray', font=('Helvetica', 8)).grid(row=1, column=1, sticky='w')

    # ── タスク操作 ────────────────────────────────────────────────────────────
    def add_task(self):
        nt = {"name": "新規タスク", "type": "WAIT", "wait_ms": 1000}
        if self.selected_index is not None:
            self.current_data["tasks"].insert(self.selected_index + 1, nt)
            self._populate_task_list()
            self.tree.selection_set(str(self.selected_index + 1))
        else:
            self.current_data["tasks"].append(nt)
            self._populate_task_list()
            self.tree.selection_set(str(len(self.current_data["tasks"]) - 1))

    def delete_task(self):
        if self.selected_index is None:
            return
        del self.current_data["tasks"][self.selected_index]
        self.selected_index = None
        self._populate_task_list()
        self._clear_dyn()

    def move_up(self):
        if self.selected_index is None or self.selected_index == 0:
            return
        idx = self.selected_index
        t = self.current_data["tasks"]
        t[idx-1], t[idx] = t[idx], t[idx-1]
        self._populate_task_list()
        self.tree.selection_set(str(idx - 1))

    def move_down(self):
        if self.selected_index is None:
            return
        t = self.current_data["tasks"]
        if self.selected_index >= len(t) - 1:
            return
        idx = self.selected_index
        t[idx+1], t[idx] = t[idx], t[idx+1]
        self._populate_task_list()
        self.tree.selection_set(str(idx + 1))

    # ── ファイル操作 ──────────────────────────────────────────────────────────
    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files","*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.current_data = json.load(f)
            if "start_trigger" not in self.current_data:
                self.current_data["start_trigger"] = {"type": "QR_ANY", "qr_data": ""}
            self._populate_task_list()
            self._populate_params()
            self._load_start_trigger()
            self.selected_index = None
            self._clear_dyn()
            messagebox.showinfo("完了", "設定を読み込みました")
        except Exception as e:
            messagebox.showerror("エラー", f"読み込み失敗:\n{e}")

    def save_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON Files","*.json")])
        if not path:
            return
        self.save_params(silent=True)
        self.current_data["start_trigger"]["type"]    = self.var_start_type.get()
        self.current_data["start_trigger"]["qr_data"] = self.var_start_qr.get()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.current_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("完了", f"保存しました:\n{path}")
        except Exception as e:
            messagebox.showerror("エラー", f"保存失敗:\n{e}")

    # ── コード生成 ────────────────────────────────────────────────────────────
    def generate_code(self):
        self.save_params(silent=True)
        self.current_data["start_trigger"]["type"]    = self.var_start_type.get()
        self.current_data["start_trigger"]["qr_data"] = self.var_start_qr.get()

        tasks_json = json.dumps(self.current_data["tasks"],         ensure_ascii=False, indent=4)
        start_json = json.dumps(self.current_data["start_trigger"], ensure_ascii=False)
        p   = self.current_data["line_params"]
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        task_mode_code = (
            "# ============================================================\n"
            "# task_mode_generated.py  ※ 自動生成 by sequence_editor.py\n"
            f"# 生成日時: {now}\n"
            "# ============================================================\n"
            "import time\n\n"
            "# シーケンス開始条件\n"
            "# type: IMMEDIATE=即時 / QR_ANY=任意QR / QR_DATA=内容指定QR\n"
            f"START_TRIGGER = {start_json}\n\n"
            "# タスク定義 (LINE_TRACE/DRIVE/ARM_MOVE/WAIT/STOP/GOAL)\n"
            f"SEQUENCE_STEPS = {tasks_json}\n\n\n"
            "class TaskSequenceMode:\n"
            "    def __init__(self, line_follower, arm_controller, uart_receiver):\n"
            "        self.lf = line_follower\n"
            "        self.arm = arm_controller\n"
            "        self.uart = uart_receiver\n"
            "        self.step_index = 0\n"
            "        self.sub_state = 'EXEC'\n"
            "        self.wait_start = 0\n"
            "        self.is_active = False\n"
            "        self._completed = False\n\n"
            "    def start(self):\n"
            "        print('[TASK] シーケンス開始')\n"
            "        self.step_index = 0\n"
            "        self.sub_state = 'EXEC'\n"
            "        self.is_active = True\n"
            "        self._completed = False\n\n"
            "    def stop(self):\n"
            "        if self.is_active: print('[TASK] シーケンス停止')\n"
            "        self.is_active = False\n"
            "        self.lf.stop()\n\n"
            "    def update(self):\n"
            "        if self.uart.consume_stop():\n"
            "            self.stop(); return\n"
            "        if not self.is_active:\n"
            "            if self._completed: return\n"
            "            st = START_TRIGGER\n"
            "            stype = st.get('type', 'QR_ANY')\n"
            "            if stype == 'IMMEDIATE': self.start()\n"
            "            elif stype == 'QR_ANY':\n"
            "                if self.uart.consume_trigger(): self.start()\n"
            "            elif stype == 'QR_DATA':\n"
            "                if self.uart.consume_trigger(st.get('qr_data', '')): self.start()\n"
            "            return\n"
            "        if self.step_index >= len(SEQUENCE_STEPS):\n"
            "            self.is_active = False; self._completed = True\n"
            "            print('[TASK] 全ステップ完了'); return\n"
            "        step = SEQUENCE_STEPS[self.step_index]\n"
            "        now = time.ticks_ms()\n"
            "        if self.sub_state == 'EXEC':\n"
            "            self._execute_step(step)\n"
            "        elif self.sub_state == 'WAIT_ARM':\n"
            "            if time.ticks_diff(now, self.wait_start) >= step.get('wait_ms', 1000):\n"
            "                self._next_step()\n"
            "        elif self.sub_state == 'WAIT_DRIVE':\n"
            "            if time.ticks_diff(now, self.wait_start) >= step.get('duration_ms', 1000):\n"
            "                self.lf.stop(); self._next_step()\n"
            "        elif self.sub_state == 'WAIT_TIME':\n"
            "            if time.ticks_diff(now, self.wait_start) >= step.get('trigger_value', 2000):\n"
            "                self.lf.stop(); self._next_step()\n"
            "        elif self.sub_state == 'WAIT_QR':\n"
            "            expected = step.get('qr_data', '')\n"
            "            if self.uart.consume_trigger(expected if expected else None):\n"
            "                self.lf.stop()\n"
            "                print(f\"[TASK] QR照合OK: '{expected}' -> 次のステップへ\")\n"
            "                self._next_step()\n"
            "        elif self.sub_state == 'WAIT_QR_ONLY':\n"
            "            expected = step.get('qr_data', '')\n"
            "            if self.uart.consume_trigger(expected if expected else None):\n"
            "                print(f\"[TASK] QRフラグ受信: '{expected}' -> 次のステップへ\")\n"
            "                self._next_step()\n"
            "        elif self.sub_state == 'WAIT_ALL_LINE':\n"
            "            if self.lf.get_sensor_pattern() == 0x0F:\n"
            "                self.lf.stop(); self._next_step()\n"
            "        elif self.sub_state == 'WAIT_WAIT':\n"
            "            if time.ticks_diff(now, self.wait_start) >= step.get('wait_ms', 1000):\n"
            "                self._next_step()\n\n"
            "    def _execute_step(self, step):\n"
            "        stype = step['type']\n"
            "        print(f\"[TASK] Step {self.step_index}: {step.get('name','')} ({stype})\")\n"
            "        if stype == 'ARM_MOVE':\n"
            "            self.arm.set_angles(step.get('arm_s1', 90), step.get('arm_s2', 90))\n"
            "            self.wait_start = time.ticks_ms(); self.sub_state = 'WAIT_ARM'\n"
            "        elif stype == 'LINE_TRACE':\n"
            "            self.lf.start_tracking()\n"
            "            self.wait_start = time.ticks_ms()\n"
            "            trigger = step.get('trigger', 'QR')\n"
            "            if trigger == 'QR': self.sub_state = 'WAIT_QR'\n"
            "            elif trigger == 'TIME': self.sub_state = 'WAIT_TIME'\n"
            "            elif trigger == 'ALL_LINE': self.sub_state = 'WAIT_ALL_LINE'\n"
            "        elif stype == 'DRIVE':\n"
            "            self.lf.start_drive(step.get('direction', 'FORWARD'), step.get('speed', None))\n"
            "            self.wait_start = time.ticks_ms(); self.sub_state = 'WAIT_DRIVE'\n"
            "        elif stype == 'WAIT_QR':\n"
            "            self.lf.stop()\n"
            "            self.sub_state = 'WAIT_QR_ONLY'\n"
            "        elif stype == 'WAIT':\n"
            "            self.lf.stop()\n"
            "            self.wait_start = time.ticks_ms(); self.sub_state = 'WAIT_WAIT'\n"
            "        elif stype == 'STOP':\n"
            "            self.lf.stop(); self._next_step()\n"
            "        elif stype == 'GOAL':\n"
            "            print('[TASK] GOAL 到達！完了。')\n"
            "            self.lf.stop(); self.is_active = False; self._completed = True\n\n"
            "    def _next_step(self):\n"
            "        self.step_index += 1; self.sub_state = 'EXEC'\n"
        )

        config_code = (
            "# ============================================================\n"
            "# config_generated.py  ※ 自動生成 by sequence_editor.py\n"
            f"# 生成日時: {now}\n"
            "# ============================================================\n"
            f"BASE_STEP_DELAY      = {p.get('BASE_STEP_DELAY', 1200)}\n"
            f"MIN_STEP_DELAY       = {p.get('MIN_STEP_DELAY', 400)}\n"
            f"MAX_STEP_DELAY       = {p.get('MAX_STEP_DELAY', 4000)}\n"
            f"LINE_KP              = {p.get('LINE_KP', 250.0)}\n"
            f"ALL_LINE_DEBOUNCE_MS = {p.get('ALL_LINE_DEBOUNCE_MS', 80)}\n"
        )

        win = tk.Toplevel(self)
        win.title("コード生成プレビュー")
        win.geometry("920x660")
        win.configure(bg=BG_COLOR)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for name, code in [("task_mode_generated.py", task_mode_code),
                           ("config_generated.py",   config_code)]:
            frm = ttk.Frame(nb); nb.add(frm, text=name)
            txt = tk.Text(frm, bg=ENTRY_BG, fg=ENTRY_FG, font=("Consolas", 9))
            txt.pack(fill=tk.BOTH, expand=True)
            txt.insert("1.0", code)
            txt.config(state="disabled")
        def save_codes():
            base = os.path.dirname(os.path.abspath(__file__))
            try:
                with open(os.path.join(base, "task_mode_generated.py"), "w", encoding="utf-8") as f:
                    f.write(task_mode_code)
                with open(os.path.join(base, "config_generated.py"), "w", encoding="utf-8") as f:
                    f.write(config_code)
                messagebox.showinfo("生成完了", f"2ファイルを保存:\n{base}")
                win.destroy()
            except Exception as e:
                messagebox.showerror("エラー", f"保存失敗:\n{e}")
        ttk.Button(win, text="✔ ファイルに保存",
                   style="Accent.TButton", command=save_codes).pack(pady=10)

    # ── シリアル通信 ──────────────────────────────────────────────────────────
    def toggle_serial(self):
        if not HAS_SERIAL:
            messagebox.showerror("エラー", "pip install pyserial"); return
        if self.serial_port and self.serial_port.is_open:
            self.running_serial = False
            self.serial_port.close(); self.serial_port = None
            self.btn_conn.config(text="接続")
            self.lbl_conn.config(text="● 未接続", foreground="gray")
            self.log("SYS", "切断")
        else:
            port = self.var_port.get(); baud = int(self.var_baud.get())
            if not port: return
            try:
                self.serial_port = serial.Serial(port, baud, timeout=1)
                self.running_serial = True
                self.btn_conn.config(text="切断")
                self.lbl_conn.config(text=f"● {port}", foreground=GREEN_COLOR)
                self.log("SYS", f"{port} ({baud}bps) 接続")
                threading.Thread(target=self._read_thread, daemon=True).start()
            except Exception as e:
                messagebox.showerror("接続エラー", f"{port}: {e}")

    def send_command(self):
        cmd = self.var_cmd.get().strip()
        if not cmd: return
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write((cmd + "\n").encode("utf-8"))
                self.log("TX", cmd)
            except Exception as e:
                self.log("ERR", str(e))
        else:
            messagebox.showwarning("警告", "未接続です")

    def _read_thread(self):
        while self.running_serial and self.serial_port and self.serial_port.is_open:
            try:
                line = self.serial_port.readline().decode("utf-8", errors="ignore").strip()
                if line: self.after(0, self.log, "RX", line)
            except Exception: break

    def log(self, prefix, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {prefix}: {msg}\n")
        self.log_text.see(tk.END)


if __name__ == "__main__":
    app = SequenceEditorApp()
    app.mainloop()
