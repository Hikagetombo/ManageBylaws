#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【デモ2】Webブラウザ型ポータルGUI (Python標準の http.server のみ使用・追加ライブラリ不要)
ご質問にあった「Webシステムのように index ページにリンクを張り、
リンク先で必要なパラメータをGUI形式で入力して実行する」仕組みをそのまま実現したデモです。

起動すると自動的にブラウザで http://localhost:8765 が開きます。
起動方法:
    python tools/demo2_web_portal.py
"""

import os
import sys
import json
import threading
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
PORT = 8765


def scan_project_files(extensions: tuple[str, ...]) -> list[str]:
    """プロジェクト内の該当拡張子ファイルを検索して相対パス一覧を返す（入力候補用）"""
    found = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 隠しフォルダや node_modules はスキップ
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for f in files:
            if f.lower().endswith(extensions):
                full_p = Path(root) / f
                try:
                    rel_p = full_p.relative_to(PROJECT_ROOT)
                    found.append(str(rel_p).replace("\\", "/"))
                except ValueError:
                    found.append(str(full_p))
    return sorted(found)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>管理組合 ツール実行ポータル (Web GUIデモ)</title>
<style>
  :root {
    --primary: #2563eb;
    --primary-hover: #1d4ed8;
    --bg: #f8fafc;
    --card-bg: #ffffff;
    --border: #e2e8f0;
    --text: #1e293b;
    --muted: #64748b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0;
    font-family: "Yu Gothic UI", "Meiryo", sans-serif;
    background: var(--bg); color: var(--text);
    line-height: 1.6;
  }
  header {
    background: #1e293b; color: #fff;
    padding: 16px 28px;
    display: flex; align-items: center; justify-content: space-between;
  }
  header h1 { margin: 0; font-size: 1.25rem; }
  header a { color: #93c5fd; text-decoration: none; font-size: 0.95rem; }
  header a:hover { text-decoration: underline; }
  .container { max-width: 960px; margin: 28px auto; padding: 0 20px; }

  /* Index カード一覧 */
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
  .card {
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 10px; padding: 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    display: flex; flex-direction: column; justify-content: space-between;
    transition: transform 0.15s, box-shadow 0.15s;
  }
  .card:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0,0,0,0.08); }
  .badge {
    display: inline-block; background: #dbeafe; color: #1e40af;
    font-size: 0.78rem; font-weight: bold; padding: 3px 10px; border-radius: 999px;
    margin-bottom: 10px;
  }
  .card h2 { margin: 0 0 10px 0; font-size: 1.15rem; }
  .card p { margin: 0 0 18px 0; color: var(--muted); font-size: 0.92rem; }
  .btn-link {
    display: inline-block; text-align: center;
    background: var(--primary); color: #fff; text-decoration: none;
    padding: 10px 16px; border-radius: 6px; font-weight: bold;
  }
  .btn-link:hover { background: var(--primary-hover); }

  /* フォーム画面 */
  .panel {
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 10px; padding: 26px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }
  .form-group { margin-bottom: 18px; }
  label { display: block; font-weight: bold; margin-bottom: 6px; font-size: 0.95rem; }
  .hint { font-size: 0.84rem; color: var(--muted); margin-top: 4px; }
  .input-row { display: flex; gap: 8px; }
  input[type="text"], select {
    width: 100%; padding: 9px 12px; border: 1px solid #cbd5e1;
    border-radius: 6px; font-size: 0.95rem;
  }
  .btn-sub {
    white-space: nowrap; padding: 9px 14px; background: #e2e8f0;
    border: 1px solid #cbd5e1; border-radius: 6px; cursor: pointer; font-weight: bold;
  }
  .btn-sub:hover { background: #cbd5e1; }
  .btn-run {
    background: var(--primary); color: #fff; border: none;
    padding: 12px 26px; font-size: 1.05rem; font-weight: bold;
    border-radius: 6px; cursor: pointer;
  }
  .btn-run:hover { background: var(--primary-hover); }
  .btn-run:disabled { background: #94a3b8; cursor: not-allowed; }

  /* 実行結果コンソール */
  .console-box {
    margin-top: 24px; background: #0f172a; color: #e2e8f0;
    padding: 16px; border-radius: 8px; font-family: Consolas, monospace;
    font-size: 0.9rem; white-space: pre-wrap; min-height: 160px; max-height: 400px;
    overflow-y: auto;
  }
  .cmd-bar {
    background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;
    padding: 8px 12px; font-family: Consolas, monospace; font-size: 0.88rem;
    margin-top: 16px; color: #334155;
  }
  .back-nav { margin-bottom: 16px; }
  .back-nav a { color: var(--primary); text-decoration: none; font-weight: bold; }
</style>
</head>
<body>
<header>
  <h1>🛠 管理組合 規約変換ツール ポータル (./tools)</h1>
  <div style="display:flex; gap:16px; align-items:center;">
    <a href="/">🏠 トップ (Index) に戻る</a>
    <button onclick="shutdownServer()" style="background:#dc2626; color:#fff; border:none; padding:6px 12px; border-radius:6px; cursor:pointer; font-weight:bold;">🛑 終了する</button>
  </div>
</header>
<div class="container">
  {{CONTENT}}
</div>
<script>
async function shutdownServer() {
  if (!confirm("ツール実行ポータルを終了しますか？")) return;
  try { await fetch('/api/shutdown', { method: 'POST' }); } catch (e) {}
  document.body.innerHTML = `
    <div style="font-family:'Yu Gothic UI',sans-serif; text-align:center; margin-top:15vh; color:#334155;">
      <h2 style="font-size:1.6rem;">✅ ポータルサーバーを正常に終了しました</h2>
      <p style="color:#64748b;">このブラウザのタブを閉じてください。</p>
    </div>
  `;
  window.close();
}

async function browseFile(inputId, mode, ext) {
  const res = await fetch(`/api/browse?mode=${mode}&ext=${encodeURIComponent(ext)}`);
  const data = await res.json();
  if (data.path) {
    document.getElementById(inputId).value = data.path;
  }
}

async function runTool(toolName, formEl) {
  const btn = formEl.querySelector('.btn-run');
  const consoleEl = document.getElementById('console-output');
  const cmdEl = document.getElementById('cmd-preview');
  btn.disabled = true;
  consoleEl.textContent = "実行中です...\\n";

  const formData = new FormData(formEl);
  const payload = { tool: toolName };
  for (const [k, v] of formData.entries()) {
    payload[k] = v;
  }
  // チェックボックス対応
  formEl.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    payload[cb.name] = cb.checked;
  });

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    cmdEl.textContent = "実行コマンド: " + (result.command || "");
    consoleEl.textContent = result.output || "(出力なし)";
    if (result.returncode === 0) {
      consoleEl.textContent += "\\n✅ 正常に完了しました (終了コード: 0)";
    } else {
      consoleEl.textContent += `\\n⚠️ エラー終了 (終了コード: ${result.returncode})`;
    }
  } catch (err) {
    consoleEl.textContent = "通信エラー: " + err;
  } finally {
    btn.disabled = false;
  }
}
</script>
</body>
</html>
"""

INDEX_CONTENT = """
<p style="margin-top:0; color:#475569;">
  実行したいプログラムを選択してください。各リンク先でパラメータや対象ファイルをGUI形式で指定して実行できます。
</p>
<div class="grid">
  <div class="card">
    <div>
      <span class="badge">convert_kiyaku_3col.py</span>
      <h2>① 4列HTML → 3列HTML 変換</h2>
      <p>4列の規約対比表HTMLから先頭1列（標準管理規約）・メニュー・HTMLコメントを削除し、3列テーブルHTMLを生成します。</p>
    </div>
    <a class="btn-link" href="/tool/3col">このツールを開く →</a>
  </div>

  <div class="card">
    <div>
      <span class="badge">convert_html_to_docx.py</span>
      <h2>② 3列HTML → Word (.docx) 変換</h2>
      <p>3列の規約対比表HTMLから中央列（改正案）のみを抽出し、Sample.docx準拠のインデント・書式でWord文書を出力します。</p>
    </div>
    <a class="btn-link" href="/tool/html2docx">このツールを開く →</a>
  </div>

  <div class="card">
    <div>
      <span class="badge">docx_to_json.py</span>
      <h2>③ Word (.docx) → JSON 変換</h2>
      <p>管理組合規約のWordファイルを解析し、章・節・条・項・号の階層構造を持つJSONファイルへ変換します。</p>
    </div>
    <a class="btn-link" href="/tool/docx2json">このツールを開く →</a>
  </div>

  <div class="card">
    <div>
      <span class="badge">json_to_docx.py</span>
      <h2>④ JSON → Word (.docx) 変換</h2>
      <p>管理組合規約のJSONファイルを読み込み、convert_html_to_docx.py と同一書式のWord文書 (.docx) を生成します。</p>
    </div>
    <a class="btn-link" href="/tool/json2docx">このツールを開く →</a>
  </div>
</div>
"""


def render_tool_page(tool_key: str) -> str:
    html_files = scan_project_files((".html", ".htm"))
    docx_files = scan_project_files((".docx",))
    json_files = scan_project_files((".json",))

    html_datalist = "".join(f'<option value="{p}">' for p in html_files)
    docx_datalist = "".join(f'<option value="{p}">' for p in docx_files)
    json_datalist = "".join(f'<option value="{p}">' for p in json_files)

    if tool_key == "3col":
        return f"""
        <div class="back-nav"><a href="/">← ツール一覧 (Index) に戻る</a></div>
        <div class="panel">
          <span class="badge">./tools/convert_kiyaku_3col.py</span>
          <h2 style="margin-top:4px;">① 規約対比表 4列HTML → 3列HTML 変換</h2>
          <datalist id="html-list">{html_datalist}</datalist>
          <form onsubmit="event.preventDefault(); runTool('3col', this);">
            <div class="form-group">
              <label>入力HTMLファイル (4列)</label>
              <div class="input-row">
                <input type="text" id="inp1" name="input_file" value="kiyaku/kiyaku-taihi-4col.html" list="html-list">
                <button type="button" class="btn-sub" onclick="browseFile('inp1', 'open', 'html')">参照...</button>
              </div>
              <div class="hint">候補から選ぶか、「参照...」ボタンでファイルを選択できます。</div>
            </div>
            <div class="form-group">
              <label>出力HTMLファイル (-o) ※空欄時は自動命名 (*-3col.html)</label>
              <div class="input-row">
                <input type="text" id="out1" name="output_file" value="" placeholder="省略時は入力と同じフォルダに 3col.html を出力">
                <button type="button" class="btn-sub" onclick="browseFile('out1', 'save', 'html')">保存先...</button>
              </div>
            </div>
            <div class="form-group" style="display:flex; gap:28px; align-items:center;">
              <div>
                <label>ヘッダー列の幅 (-w)</label>
                <select name="col_width" style="width:140px;">
                  <option value="33%" selected>33% (標準)</option>
                  <option value="30%">30%</option>
                  <option value="25%">25%</option>
                </select>
              </div>
              <div style="padding-top:18px;">
                <label style="font-weight:normal; cursor:pointer;">
                  <input type="checkbox" name="table_only">
                  外枠HTMLを含めず <code>&lt;table&gt;</code> タグのみ出力する (-t)
                </label>
              </div>
            </div>
            <button type="submit" class="btn-run">▶ 変換を実行する</button>
          </form>
          <div id="cmd-preview" class="cmd-bar">実行コマンド: (未実行)</div>
          <div id="console-output" class="console-box">ここに実行ログが表示されます。</div>
        </div>
        """

    elif tool_key == "html2docx":
        return f"""
        <div class="back-nav"><a href="/">← ツール一覧 (Index) に戻る</a></div>
        <div class="panel">
          <span class="badge">./tools/convert_html_to_docx.py</span>
          <h2 style="margin-top:4px;">② 規約対比表 3列HTML → Microsoft Word (.docx) 変換</h2>
          <datalist id="html-list">{html_datalist}</datalist>
          <form onsubmit="event.preventDefault(); runTool('html2docx', this);">
            <div class="form-group">
              <label>入力HTMLファイル (-i)</label>
              <div class="input-row">
                <input type="text" id="inp2" name="input_file" value="Release/kiyaku-taihi-3col.html" list="html-list">
                <button type="button" class="btn-sub" onclick="browseFile('inp2', 'open', 'html')">参照...</button>
              </div>
            </div>
            <div class="form-group">
              <label>出力Wordファイル (-o)</label>
              <div class="input-row">
                <input type="text" id="out2" name="output_file" value="改正規約.docx">
                <button type="button" class="btn-sub" onclick="browseFile('out2', 'save', 'docx')">保存先...</button>
              </div>
            </div>
            <button type="submit" class="btn-run">▶ Word (.docx) 変換を実行する</button>
          </form>
          <div id="cmd-preview" class="cmd-bar">実行コマンド: (未実行)</div>
          <div id="console-output" class="console-box">ここに実行ログが表示されます。</div>
        </div>
        """

    elif tool_key == "docx2json":
        default_docx = "convt/1ブロック規約（2013年）.docx" if "convt/1ブロック規約（2013年）.docx" in docx_files else "1ブロック規約（2013年）.docx"
        return f"""
        <div class="back-nav"><a href="/">← ツール一覧 (Index) に戻る</a></div>
        <div class="panel">
          <span class="badge">./tools/docx_to_json.py</span>
          <h2 style="margin-top:4px;">③ 管理組合規約 Word (.docx) → JSON 変換</h2>
          <datalist id="docx-list">{docx_datalist}</datalist>
          <form onsubmit="event.preventDefault(); runTool('docx2json', this);">
            <div class="form-group">
              <label>入力Wordファイル (.docx)</label>
              <div class="input-row">
                <input type="text" id="inp3" name="input_file" value="{default_docx}" list="docx-list">
                <button type="button" class="btn-sub" onclick="browseFile('inp3', 'open', 'docx')">参照...</button>
              </div>
              <div class="hint">入力欄をクリックするとプロジェクト内の .docx ファイル候補が表示されます。</div>
            </div>
            <div class="form-group">
              <label>出力JSONファイル ※空欄時は入力ファイル名.json</label>
              <div class="input-row">
                <input type="text" id="out3" name="output_file" value="" placeholder="省略時は入力ファイルと同じ場所に .json を出力">
                <button type="button" class="btn-sub" onclick="browseFile('out3', 'save', 'json')">保存先...</button>
              </div>
            </div>
            <button type="submit" class="btn-run">▶ JSON 変換を実行する</button>
          </form>
          <div id="cmd-preview" class="cmd-bar">実行コマンド: (未実行)</div>
          <div id="console-output" class="console-box">ここに実行ログが表示されます。</div>
        </div>
        """

    elif tool_key == "json2docx":
        return f"""
        <div class="back-nav"><a href="/">← ツール一覧 (Index) に戻る</a></div>
        <div class="panel">
          <span class="badge">./tools/json_to_docx.py</span>
          <h2 style="margin-top:4px;">④ 管理組合規約 JSON → Word (.docx) 変換</h2>
          <datalist id="json-list">{json_datalist}</datalist>
          <form onsubmit="event.preventDefault(); runTool('json2docx', this);">
            <div class="form-group">
              <label>入力JSONファイル (.json)</label>
              <div class="input-row">
                <input type="text" id="inp4" name="input_file" value="管理組合規約.json" list="json-list">
                <button type="button" class="btn-sub" onclick="browseFile('inp4', 'open', 'json')">参照...</button>
              </div>
              <div class="hint">入力欄をクリックするとプロジェクト内の .json ファイル候補が表示されます。</div>
            </div>
            <div class="form-group">
              <label>出力Wordファイル (.docx) ※空欄時は入力ファイル名.docx</label>
              <div class="input-row">
                <input type="text" id="out4" name="output_file" value="" placeholder="省略時は入力ファイルと同じ場所に .docx を出力">
                <button type="button" class="btn-sub" onclick="browseFile('out4', 'save', 'docx')">保存先...</button>
              </div>
            </div>
            <button type="submit" class="btn-run">▶ Word (.docx) 変換を実行する</button>
          </form>
          <div id="cmd-preview" class="cmd-bar">実行コマンド: (未実行)</div>
          <div id="console-output" class="console-box">ここに実行ログが表示されます。</div>
        </div>
        """
    return "<p>ページが見つかりません</p>"


class PortalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # コンソールを汚さないようアクセスログを簡潔化
        pass

    def _send_html(self, content_body: str):
        page = HTML_TEMPLATE.replace("{{CONTENT}}", content_body)
        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj: dict):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_html(INDEX_CONTENT)
        elif path.startswith("/tool/"):
            tool_key = path.split("/tool/")[-1]
            self._send_html(render_tool_page(tool_key))
        elif path == "/api/browse":
            qs = parse_qs(parsed.query)
            mode = qs.get("mode", ["open"])[0]
            ext = qs.get("ext", ["*"])[0]
            selected = self._open_native_dialog(mode, ext)
            self._send_json({"path": selected})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/shutdown":
            self._send_json({"status": "shutting_down"})
            threading.Timer(0.3, lambda: os._exit(0)).start()
            return
        if self.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            tool = body.get("tool")
            cmd = [sys.executable]

            if tool == "3col":
                cmd.append(str(TOOLS_DIR / "convert_kiyaku_3col.py"))
                if body.get("input_file", "").strip():
                    cmd.append(body["input_file"].strip())
                if body.get("output_file", "").strip():
                    cmd.extend(["-o", body["output_file"].strip()])
                if body.get("table_only"):
                    cmd.append("-t")
                w = body.get("col_width", "33%").strip()
                if w and w != "33%":
                    cmd.extend(["-w", w])

            elif tool == "html2docx":
                cmd.append(str(TOOLS_DIR / "convert_html_to_docx.py"))
                inp = body.get("input_file", "").strip() or "Release/kiyaku-taihi-3col.html"
                out = body.get("output_file", "").strip() or "改正規約.docx"
                cmd.extend(["-i", inp, "-o", out])

            elif tool == "docx2json":
                cmd.append(str(TOOLS_DIR / "docx_to_json.py"))
                inp = body.get("input_file", "").strip()
                out = body.get("output_file", "").strip()
                if inp:
                    cmd.append(inp)
                if inp and out:
                    cmd.append(out)

            elif tool == "json2docx":
                cmd.append(str(TOOLS_DIR / "json_to_docx.py"))
                inp = body.get("input_file", "").strip()
                out = body.get("output_file", "").strip()
                if inp:
                    cmd.extend(["-i", inp])
                if out:
                    cmd.extend(["-o", out])

            cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env
            )
            self._send_json({
                "command": cmd_str,
                "output": proc.stdout,
                "returncode": proc.returncode
            })
        else:
            self.send_error(404)

    def _open_native_dialog(self, mode: str, ext: str) -> str:
        """ブラウザの「参照...」ボタンからWindows標準のファイル選択ダイアログを開く"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            ft_map = {
                "html": [("HTMLファイル", "*.html;*.htm"), ("すべて", "*.*")],
                "docx": [("Word文書", "*.docx"), ("すべて", "*.*")],
                "json": [("JSONファイル", "*.json"), ("すべて", "*.*")],
            }
            filetypes = ft_map.get(ext, [("すべて", "*.*")])
            if mode == "save":
                p = filedialog.asksaveasfilename(
                    initialdir=str(PROJECT_ROOT),
                    defaultextension=f".{ext}",
                    filetypes=filetypes
                )
            else:
                p = filedialog.askopenfilename(
                    initialdir=str(PROJECT_ROOT),
                    filetypes=filetypes
                )
            root.destroy()
            return p or ""
        except Exception:
            return ""


def main():
    url = f"http://localhost:{PORT}/"
    print("=" * 60)
    print(" 管理組合 ツール実行ポータル (Web GUIデモ) を起動しました")
    print(f" URL: {url}")
    print(" 終了するには Ctrl + C を押すか、このウィンドウを閉じてください。")
    print("=" * 60)
    webbrowser.open(url)
    server = HTTPServer(("127.0.0.1", PORT), PortalHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバーを停止しました。")


if __name__ == "__main__":
    main()
