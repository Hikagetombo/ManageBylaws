#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【デモ1】デスクトップGUIランチャー (Python標準の tkinter / ttk を使用)
追加ライブラリのインストール不要で、./tools 内の3つのCLIプログラムを
GUI画面（タブ切り替え・ファイル選択ダイアログ・ボタン操作）から実行できます。

起動方法:
    python tools/demo1_desktop_gui.py
"""

import os
import sys
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent


class ToolLauncherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("管理組合 規約変換ツール集 (デスクトップGUI版)")
        self.geometry("820x680")
        self.minsize(720, 580)

        # Windowsで見やすいフォントとスタイル設定
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure(".", font=("Yu Gothic UI", 10))
        style.configure("TNotebook.Tab", font=("Yu Gothic UI", 10, "bold"), padding=(14, 6))
        style.configure("Header.TLabel", font=("Yu Gothic UI", 13, "bold"))
        style.configure("Desc.TLabel", font=("Yu Gothic UI", 9), foreground="#444444")
        style.configure("Run.TButton", font=("Yu Gothic UI", 11, "bold"), padding=(12, 8))

        self._build_ui()

    def _build_ui(self):
        # 上部ヘッダー
        header_frame = ttk.Frame(self, padding=(16, 12, 16, 4))
        header_frame.pack(fill=tk.X)
        ttk.Label(
            header_frame,
            text="管理組合 規約変換ツール ランチャー",
            style="Header.TLabel"
        ).pack(anchor=tk.W)
        ttk.Label(
            header_frame,
            text="実行したい変換ツールをタブから選び、ファイルや条件を指定して「変換を実行する」ボタンを押してください。",
            style="Desc.TLabel"
        ).pack(anchor=tk.W, pady=(2, 0))

        # タブ（Notebook）: Webの index から各ページへ移動する感覚で切り替え
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.X, padx=16, pady=8)

        self._create_tab_4col_to_3col()
        self._create_tab_html_to_docx()
        self._create_tab_docx_to_json()
        self._create_tab_json_to_docx()

        # 下部: 実行コマンドプレビュー ＆ 実行ログ表示エリア
        log_frame = ttk.LabelFrame(self, text=" 実行状況・出力ログ ", padding=(12, 8))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 14))

        cmd_bar = ttk.Frame(log_frame)
        cmd_bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(cmd_bar, text="実行コマンド:").pack(side=tk.LEFT)
        self.cmd_preview_var = tk.StringVar(value="（ここに実行されたCLIコマンドが表示されます）")
        cmd_entry = ttk.Entry(cmd_bar, textvariable=self.cmd_preview_var, state="readonly", font=("Consolas", 9))
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        ttk.Button(cmd_bar, text="ログ消去", command=self._clear_log).pack(side=tk.RIGHT)

        self.log_text = ScrolledText(
            log_frame,
            height=12,
            font=("Consolas", 10),
            bg="#1e1e1e",
            fg="#e0e0e0",
            insertbackground="white",
            relief=tk.FLAT,
            padx=8,
            pady=8
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._append_log("準備完了。上のタブからツールを選択して実行してください。\n")

    # =========================================================================
    # タブ1: convert_kiyaku_3col.py (4列HTML -> 3列HTML)
    # =========================================================================
    def _create_tab_4col_to_3col(self):
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=" ① 4列HTML → 3列HTML ")

        ttk.Label(
            tab,
            text="【convert_kiyaku_3col.py】 4列の規約対比表HTMLから先頭1列・メニュー・コメントを除去し、3列HTMLを生成します。",
            style="Desc.TLabel"
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 12))

        # 入力ファイル
        ttk.Label(tab, text="入力HTMLファイル (4列):").grid(row=1, column=0, sticky=tk.W, pady=6)
        self.t1_input_var = tk.StringVar(value="kiyaku/kiyaku-taihi-4col.html")
        ttk.Entry(tab, textvariable=self.t1_input_var, width=55).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="参照...",
            command=lambda: self._browse_open(self.t1_input_var, [("HTMLファイル", "*.html;*.htm"), ("すべて", "*.*")])
        ).grid(row=1, column=2, pady=6)

        # 出力ファイル
        ttk.Label(tab, text="出力HTMLファイル (省略時自動):").grid(row=2, column=0, sticky=tk.W, pady=6)
        self.t1_output_var = tk.StringVar(value="")
        ttk.Entry(tab, textvariable=self.t1_output_var, width=55).grid(row=2, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="保存先...",
            command=lambda: self._browse_save(self.t1_output_var, ".html", [("HTMLファイル", "*.html")])
        ).grid(row=2, column=2, pady=6)

        # オプション: 列幅 & テーブルのみ
        opt_frame = ttk.Frame(tab)
        opt_frame.grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=8, pady=6)

        ttk.Label(opt_frame, text="ヘッダー列幅 (-w):").pack(side=tk.LEFT)
        self.t1_width_var = tk.StringVar(value="33%")
        ttk.Combobox(
            opt_frame, textvariable=self.t1_width_var, values=["33%", "30%", "25%", "auto"], width=10
        ).pack(side=tk.LEFT, padx=(6, 20))

        self.t1_table_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_frame,
            text="テーブルタグ (<table>) のみ出力する (-t)",
            variable=self.t1_table_only_var
        ).pack(side=tk.LEFT)

        # 実行ボタン
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=(14, 2))
        ttk.Button(
            btn_frame,
            text="▶ 4列 → 3列HTML 変換を実行する",
            style="Run.TButton",
            command=self._run_tool1
        ).pack()

        tab.columnconfigure(1, weight=1)

    def _run_tool1(self):
        script = str(TOOLS_DIR / "convert_kiyaku_3col.py")
        cmd = [sys.executable, script]

        inp = self.t1_input_var.get().strip()
        if inp:
            cmd.append(inp)

        out = self.t1_output_var.get().strip()
        if out:
            cmd.extend(["-o", out])

        if self.t1_table_only_var.get():
            cmd.append("-t")

        width = self.t1_width_var.get().strip()
        if width and width != "33%":
            cmd.extend(["-w", width])

        self._execute_command(cmd)

    # =========================================================================
    # タブ2: convert_html_to_docx.py (3列HTML -> 改正規約.docx)
    # =========================================================================
    def _create_tab_html_to_docx(self):
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=" ② 3列HTML → Word(.docx) ")

        ttk.Label(
            tab,
            text="【convert_html_to_docx.py】 3列の対比表HTMLから中央列（改正案）を抽出し、規定書式のWord文書(.docx)を作成します。",
            style="Desc.TLabel"
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 12))

        # 入力HTML
        ttk.Label(tab, text="入力HTMLファイル (-i):").grid(row=1, column=0, sticky=tk.W, pady=6)
        self.t2_input_var = tk.StringVar(value="Release/kiyaku-taihi-3col.html")
        ttk.Entry(tab, textvariable=self.t2_input_var, width=55).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="参照...",
            command=lambda: self._browse_open(self.t2_input_var, [("HTMLファイル", "*.html;*.htm"), ("すべて", "*.*")])
        ).grid(row=1, column=2, pady=6)

        # 出力Docx
        ttk.Label(tab, text="出力Wordファイル (-o):").grid(row=2, column=0, sticky=tk.W, pady=6)
        self.t2_output_var = tk.StringVar(value="改正規約.docx")
        ttk.Entry(tab, textvariable=self.t2_output_var, width=55).grid(row=2, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="保存先...",
            command=lambda: self._browse_save(self.t2_output_var, ".docx", [("Word文書", "*.docx")])
        ).grid(row=2, column=2, pady=6)

        # 実行ボタン
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(20, 2))
        ttk.Button(
            btn_frame,
            text="▶ HTML → Word (.docx) 変換を実行する",
            style="Run.TButton",
            command=self._run_tool2
        ).pack()

        tab.columnconfigure(1, weight=1)

    def _run_tool2(self):
        script = str(TOOLS_DIR / "convert_html_to_docx.py")
        inp = self.t2_input_var.get().strip() or "Release/kiyaku-taihi-3col.html"
        out = self.t2_output_var.get().strip() or "改正規約.docx"
        cmd = [sys.executable, script, "-i", inp, "-o", out]
        self._execute_command(cmd)

    # =========================================================================
    # タブ3: docx_to_json.py (Word .docx -> JSON)
    # =========================================================================
    def _create_tab_docx_to_json(self):
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=" ③ Word(.docx) → JSON ")

        ttk.Label(
            tab,
            text="【docx_to_json.py】 管理組合規約のWordファイル(.docx)を解析し、章・節・条・項・号の階層JSONに変換します。",
            style="Desc.TLabel"
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 12))

        # デフォルトで convt フォルダ内の docx があれば初期値にセット
        default_docx = PROJECT_ROOT / "convt" / "1ブロック規約（2013年）.docx"
        init_docx_str = str(default_docx) if default_docx.exists() else "1ブロック規約（2013年）.docx"

        # 入力Docx
        ttk.Label(tab, text="入力Wordファイル (.docx):").grid(row=1, column=0, sticky=tk.W, pady=6)
        self.t3_input_var = tk.StringVar(value=init_docx_str)
        ttk.Entry(tab, textvariable=self.t3_input_var, width=55).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="参照...",
            command=lambda: self._browse_open(self.t3_input_var, [("Word文書", "*.docx"), ("すべて", "*.*")])
        ).grid(row=1, column=2, pady=6)

        # 出力JSON
        ttk.Label(tab, text="出力JSONファイル (省略時自動):").grid(row=2, column=0, sticky=tk.W, pady=6)
        self.t3_output_var = tk.StringVar(value="")
        ttk.Entry(tab, textvariable=self.t3_output_var, width=55).grid(row=2, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="保存先...",
            command=lambda: self._browse_save(self.t3_output_var, ".json", [("JSONファイル", "*.json")])
        ).grid(row=2, column=2, pady=6)

        # 実行ボタン
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(20, 2))
        ttk.Button(
            btn_frame,
            text="▶ Word (.docx) → JSON 変換を実行する",
            style="Run.TButton",
            command=self._run_tool3
        ).pack()

        tab.columnconfigure(1, weight=1)

    def _run_tool3(self):
        script = str(TOOLS_DIR / "docx_to_json.py")
        cmd = [sys.executable, script]

        inp = self.t3_input_var.get().strip()
        if inp:
            cmd.append(inp)
        out = self.t3_output_var.get().strip()
        if out:
            if not inp:
                messagebox.showwarning("入力確認", "出力ファイルを指定する場合は、入力Wordファイルも指定してください。")
                return
            cmd.append(out)

        self._execute_command(cmd)

    # =========================================================================
    # タブ4: json_to_docx.py (JSON -> Word .docx)
    # =========================================================================
    def _create_tab_json_to_docx(self):
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text=" ④ JSON → Word(.docx) ")

        ttk.Label(
            tab,
            text="【json_to_docx.py】 規約の階層JSONファイル(.json)から、convert_html_to_docx.py と同一書式のWord文書(.docx)を生成します。",
            style="Desc.TLabel"
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 12))

        default_json = PROJECT_ROOT / "管理組合規約.json"
        init_json_str = str(default_json) if default_json.exists() else "管理組合規約.json"

        # 入力JSON
        ttk.Label(tab, text="入力JSONファイル (-i):").grid(row=1, column=0, sticky=tk.W, pady=6)
        self.t4_input_var = tk.StringVar(value=init_json_str)
        ttk.Entry(tab, textvariable=self.t4_input_var, width=55).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="参照...",
            command=lambda: self._browse_open(self.t4_input_var, [("JSONファイル", "*.json"), ("すべて", "*.*")])
        ).grid(row=1, column=2, pady=6)

        # 出力Docx
        ttk.Label(tab, text="出力Wordファイル (-o 省略時自動):").grid(row=2, column=0, sticky=tk.W, pady=6)
        self.t4_output_var = tk.StringVar(value="")
        ttk.Entry(tab, textvariable=self.t4_output_var, width=55).grid(row=2, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(
            tab, text="保存先...",
            command=lambda: self._browse_save(self.t4_output_var, ".docx", [("Word文書", "*.docx")])
        ).grid(row=2, column=2, pady=6)

        # 実行ボタン
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(20, 2))
        ttk.Button(
            btn_frame,
            text="▶ JSON → Word (.docx) 変換を実行する",
            style="Run.TButton",
            command=self._run_tool4
        ).pack()

        tab.columnconfigure(1, weight=1)

    def _run_tool4(self):
        script = str(TOOLS_DIR / "json_to_docx.py")
        cmd = [sys.executable, script]

        inp = self.t4_input_var.get().strip()
        if inp:
            cmd.extend(["-i", inp])
        out = self.t4_output_var.get().strip()
        if out:
            cmd.extend(["-o", out])

        self._execute_command(cmd)

    # =========================================================================
    # 共通ヘルパー（ファイルダイアログ ＆ 非同期コマンド実行）
    # =========================================================================
    def _browse_open(self, target_var: tk.StringVar, filetypes):
        path = filedialog.askopenfilename(
            initialdir=str(PROJECT_ROOT),
            title="入力ファイルを選択",
            filetypes=filetypes
        )
        if path:
            target_var.set(path)

    def _browse_save(self, target_var: tk.StringVar, defaultext: str, filetypes):
        path = filedialog.asksaveasfilename(
            initialdir=str(PROJECT_ROOT),
            title="出力ファイルの保存先を指定",
            defaultextension=defaultext,
            filetypes=filetypes
        )
        if path:
            target_var.set(path)

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def _append_log(self, text: str):
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    def _execute_command(self, cmd: list[str]):
        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        self.cmd_preview_var.set(cmd_str)
        self._append_log(f"\n>>> 実行開始: {cmd_str}\n")

        def worker():
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env
                )
                for line in proc.stdout:
                    self.after(0, self._append_log, line)
                proc.wait()
                if proc.returncode == 0:
                    self.after(0, self._append_log, "=== 正常に完了しました (終了コード: 0) ===\n")
                else:
                    self.after(0, self._append_log, f"=== エラーで終了しました (終了コード: {proc.returncode}) ===\n")
            except Exception as e:
                self.after(0, self._append_log, f"[実行例外エラー]: {e}\n")

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = ToolLauncherGUI()
    app.mainloop()
