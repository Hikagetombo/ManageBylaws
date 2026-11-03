# 🏢 管理組合 規約変換ツール集 (ManageBylaws)

管理組合規約の対比表（HTML）・Word文書（`.docx`）・階層データ（`.json`）を相互変換するためのツール集です。
Python環境がないパソコンからでも、以下のリンクからブラウザ上でGUI操作（ファイルのドラッグ＆ドロップとダウンロード）で変換を実行できます。

---

## 🚀 Webアプリ（GUI）の起動

以下のボタンまたはリンクをクリックすると、ブラウザ上で変換ツールが起動します。

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://managebylaws-dne7u2nsa7k2hgv6pcsmkn.streamlit.app/)

* **WebアプリURL**: [https://managebylaws-dne7u2nsa7k2hgv6pcsmkn.streamlit.app/](https://managebylaws-dne7u2nsa7k2hgv6pcsmkn.streamlit.app/)

> **💡 アクセス時に「Zzz... (This app has gone to sleep)」と表示された場合**
> しばらくアクセスがない場合、クラウドサーバーが省電力モード（スリープ）になります。画面中央の青い **「Yes, get this app back up!」** ボタンを押して数十秒お待ちいただくと通常通り起動します。

---

## 🛠 収録されている変換ツール（`./tools`）

サイドバーのメニューから以下の4つのツールを切り替えて使用できます。

| メニュー | プログラム名 | 入力ファイル | 出力ファイル | 内容・主な仕様 |
| :--- | :--- | :--- | :--- | :--- |
| **① 4列HTML → 3列HTML** | `convert_kiyaku_3col.py` | 4列対比表 (`.html`) | 3列対比表 (`.html`) | 先頭1列（マンション標準管理規約）・メニュー・HTMLコメントを除去し、3列テーブルHTMLを生成します。 |
| **② 3列HTML → Word(.docx)** | `convert_html_to_docx.py` | 3列対比表 (`.html`) | 改正規約 (`.docx`) | 3列対比表の中央列（改正案）を抽出し、規定書式（ＭＳ 明朝 12pt・ぶら下げインデント）のWord文書を生成します。 |
| **③ Word(.docx) → JSON** | `docx_to_json.py` | 規約Word (`.docx`) | 規約データ (`.json`) | Word文書を解析し、章・節・条・項・号・細目の階層構造を持つJSONファイルへ変換します。 |
| **④ JSON → Word(.docx)** | `json_to_docx.py` | 規約データ (`.json`) | 改正規約 (`.docx`) | 階層構造のJSONデータから、`convert_html_to_docx.py` と同一書式のWord文書を生成します。 |

---

## 💻 ローカルPCで起動する場合

Windows PCの手元で動かす場合は、`tools` フォルダ内のバッチファイルをダブルクリックするだけで起動できます。

* `tools/3_Streamlit版起動.bat` : Streamlit版Web GUIをローカルで起動
* `tools/2_WebポータルGUI起動.bat` : Python標準ライブラリのみで動作するローカルWebポータルを起動
* `tools/1_デスクトップGUI起動.bat` : Windows標準ウィンドウ（Tkinter）版のGUIランチャーを起動
