#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【デモ3】Streamlit Webアプリ版 (HTML/CSSを一切書かずにPythonだけでWeb GUIを作る方式)
ファイルのドラッグ＆ドロップによるアップロードと、変換結果のワンクリックダウンロードに対応しています。

起動方法:
    streamlit run tools/demo3_streamlit_app.py
"""

import os
import sys
import tempfile
import threading
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

# ./tools 内のモジュールを直接インポートできるようにパス追加
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from convert_kiyaku_3col import convert_4col_to_3col
from convert_html_to_docx import convert_html_to_docx
from docx_to_json import convert_docx_to_json
from json_to_docx import convert_json_to_docx

st.set_page_config(page_title="管理組合 規約変換ツール集", page_icon="🏢", layout="wide")

# サイドバー（Indexメニュー）
st.sidebar.title("🏢 規約変換ツール集")
page = st.sidebar.radio(
    "使用するツールを選択:",
    [
        "🏠 トップ (ツール一覧)",
        "① 4列HTML → 3列HTML",
        "② 3列HTML → Word(.docx)",
        "③ Word(.docx) → JSON",
        "④ JSON → Word(.docx)",
    ]
)

st.sidebar.divider()
if st.sidebar.button("🛑 アプリを終了する", use_container_width=True):
    # Streamlitの「Connection error」ダイアログが出ないよう、画面全体を終了メッセージに書き換えてから停止
    components.html(
        """
        <script>
        try {
            window.parent.document.title = "終了しました";
            window.parent.document.body.innerHTML = `
                <div style="font-family:'Yu Gothic UI',sans-serif; text-align:center; margin-top:15vh; color:#334155;">
                    <h2 style="font-size:1.6rem;">✅ アプリケーションを正常に終了しました</h2>
                    <p style="color:#64748b;">バックグラウンドのPythonサーバーは停止しました。このブラウザのタブを閉じてください。</p>
                </div>
            `;
            window.parent.close();
        } catch (e) {}
        </script>
        """,
        height=0,
    )
    threading.Timer(0.8, lambda: os._exit(0)).start()
    st.stop()

if page == "🏠 トップ (ツール一覧)":
    st.title("管理組合 規約変換ツール ポータル (Streamlit版)")
    st.markdown(
        """
        左側のサイドバーから実行したい変換プログラムを選択してください。
        **ファイルのドラッグ＆ドロップ**だけで変換を実行し、結果ファイルをダウンロードできます。

        ---
        ### 収録ツール一覧 (`./tools`)
        1. **`convert_kiyaku_3col.py` (4列HTML → 3列HTML)**
           * 4列の対比表HTMLから1列目（標準管理規約）・メニュー・コメントを除去して3列HTMLを作成します。
        2. **`convert_html_to_docx.py` (3列HTML → Word `.docx`)**
           * 3列の対比表HTMLから中央列（改正案）を抽出し、規定書式のWord文書を作成します。
        3. **`docx_to_json.py` (Word `.docx` → JSON)**
           * 管理組合規約のWord文書を解析し、階層構造のJSONデータを出力します。
        4. **`json_to_docx.py` (JSON → Word `.docx`)**
           * 階層構造のJSONデータから、`convert_html_to_docx.py` と同一書式（ＭＳ 明朝 12pt・ぶら下げインデント）のWord文書を作成します。
        """
    )

elif page == "① 4列HTML → 3列HTML":
    st.header("① 規約対比表 4列HTML → 3列HTML 変換")
    st.caption("対象スクリプト: `./tools/convert_kiyaku_3col.py`")

    uploaded = st.file_uploader("4列のHTMLファイルをドラッグ＆ドロップ（または選択）", type=["html", "htm"])
    col1, col2 = st.columns(2)
    with col1:
        col_width = st.selectbox("ヘッダー列の幅 (-w)", ["33%", "30%", "25%"], index=0)
    with col2:
        table_only = st.checkbox("外枠HTMLを省き <table> タグのみ出力する (-t)", value=False)

    if st.button("▶ 3列HTMLに変換する", type="primary", disabled=(uploaded is None)):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = Path(tmpdir) / uploaded.name
            out_path = Path(tmpdir) / uploaded.name.replace("4col", "3col")
            if out_path == in_path:
                out_path = Path(tmpdir) / f"{in_path.stem}-3col.html"

            in_path.write_bytes(uploaded.getvalue())
            convert_4col_to_3col(str(in_path), str(out_path), table_only=table_only, col_width=col_width)

            result_bytes = out_path.read_bytes()
            st.success(f"変換が完了しました！ ({out_path.name})")
            st.download_button(
                label=f"📥 {out_path.name} をダウンロード",
                data=result_bytes,
                file_name=out_path.name,
                mime="text/html",
            )

elif page == "② 3列HTML → Word(.docx)":
    st.header("② 規約対比表 3列HTML → Word (.docx) 変換")
    st.caption("対象スクリプト: `./tools/convert_html_to_docx.py`")

    uploaded = st.file_uploader("3列のHTMLファイルをドラッグ＆ドロップ（または選択）", type=["html", "htm"])
    out_name = st.text_input("出力するWordファイル名 (-o)", value="改正規約.docx")

    if st.button("▶ Word (.docx) に変換する", type="primary", disabled=(uploaded is None)):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = Path(tmpdir) / uploaded.name
            out_path = Path(tmpdir) / (out_name or "改正規約.docx")
            in_path.write_bytes(uploaded.getvalue())

            convert_html_to_docx(str(in_path), str(out_path))
            result_bytes = out_path.read_bytes()

            st.success("Word文書の生成が完了しました！")
            st.download_button(
                label=f"📥 {out_path.name} をダウンロード",
                data=result_bytes,
                file_name=out_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

elif page == "③ Word(.docx) → JSON":
    st.header("③ 管理組合規約 Word (.docx) → JSON 変換")
    st.caption("対象スクリプト: `./tools/docx_to_json.py`")

    uploaded = st.file_uploader("規約のWordファイル (.docx) をドラッグ＆ドロップ", type=["docx"])

    if st.button("▶ JSON に変換する", type="primary", disabled=(uploaded is None)):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = Path(tmpdir) / uploaded.name
            out_path = in_path.with_suffix(".json")
            in_path.write_bytes(uploaded.getvalue())

            data = convert_docx_to_json(in_path, out_path)
            total_articles = sum(
                len(sec["articles"]) for chap in data["chapters"] for sec in chap["sections"]
            )
            result_text = out_path.read_text(encoding="utf-8")

            st.success(f"変換完了！ (章数: {len(data['chapters'])}, 条数: {total_articles})")
            st.download_button(
                label=f"📥 {out_path.name} をダウンロード",
                data=result_text.encode("utf-8"),
                file_name=out_path.name,
                mime="application/json",
            )
            with st.expander("生成されたJSONのプレビューを表示"):
                st.json(data)

elif page == "④ JSON → Word(.docx)":
    st.header("④ 管理組合規約 JSON → Word (.docx) 変換")
    st.caption("対象スクリプト: `./tools/json_to_docx.py`")

    uploaded = st.file_uploader("規約のJSONファイル (.json) をドラッグ＆ドロップ", type=["json"])
    default_out_name = Path(uploaded.name).with_suffix(".docx").name if uploaded else "改正規約.docx"
    out_name = st.text_input("出力するWordファイル名 (-o)", value=default_out_name)

    if st.button("▶ Word (.docx) に変換する", type="primary", disabled=(uploaded is None)):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = Path(tmpdir) / uploaded.name
            out_path = Path(tmpdir) / (out_name or "改正規約.docx")
            in_path.write_bytes(uploaded.getvalue())

            data = convert_json_to_docx(in_path, out_path)
            total_articles = sum(
                len(sec["articles"]) for chap in data.get("chapters", []) for sec in chap.get("sections", [])
            )
            result_bytes = out_path.read_bytes()

            st.success(f"Word文書の生成が完了しました！ (章数: {len(data.get('chapters', []))}, 条数: {total_articles})")
            st.download_button(
                label=f"📥 {out_path.name} をダウンロード",
                data=result_bytes,
                file_name=out_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
