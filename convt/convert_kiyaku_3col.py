#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
規約対比表 4列HTML -> 3列HTML 変換プログラム (convert_kiyaku_3col.py)

【仕様】
1. 入力ファイル: kiyaku/kiyaku-taihi-4col.html（デフォルト最優先）
2. メニュー（<nav>）やテーブル外の見出しを削除し、テーブル部分のみを配置
3. 4列あるテーブルの先頭1列（マンション標準管理規約）を削除し、
   ・新1列目: グランピア西白井（1ブロック）
   ・新2列目: 改正案
   ・新3列目: 説明/コメント（確実に完全保持）
   の3列テーブルとする
4. HTMLコメント（<!-- ... -->）をすべて削除
5. テーブルヘッダーの幅を 33% に調整
"""

import os
import sys
import re
import argparse
from bs4 import BeautifulSoup, Comment

# Windowsコンソールでの文字化け防止
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def find_default_input():
    """入力ファイルが省略された場合の候補を検索（kiyaku/kiyaku-taihi-4col.html を優先）"""
    candidates = [
        "kiyaku/kiyaku-taihi-4col.html",
        "kiyaku-taihi-4col.html",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def convert_4col_to_3col(input_path, output_path=None, table_only=False, col_width="33%"):
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    input_path = os.path.normpath(input_path)

    # 出力ファイルパスの自動決定（入力と同じディレクトリの 3col.html）
    if not output_path:
        input_dir = os.path.dirname(input_path)
        base_name = os.path.basename(input_path)
        if "4col" in base_name:
            out_name = base_name.replace("4col", "3col")
        else:
            name_part, ext = os.path.splitext(base_name)
            out_name = f"{name_part}-3col{ext}"
        output_path = os.path.join(input_dir, out_name) if input_dir else out_name
    output_path = os.path.normpath(output_path)

    print("=" * 65)
    print(f"【入力ファイル】: {input_path}")
    print(f"【出力ファイル】: {output_path}")
    print("=" * 65)

    print("[1/5] 入力ファイルを読み込み中...")
    with open(input_path, "r", encoding="utf-8") as f:
        html_text = f.read()

    # パーサー選択 (lxml を優先)
    try:
        import lxml
        parser = "lxml"
    except ImportError:
        parser = "html.parser"

    soup = BeautifulSoup(html_text, parser)

    # 1. HTMLコメントをすべて削除
    print("[2/5] HTMLコメント（<!-- ... -->）を削除中...")
    comments = soup.find_all(string=lambda t: isinstance(t, Comment))
    del_comment_count = len(comments)
    for c in comments:
        c.extract()
    print(f"      -> 削除したHTMLコメント数: {del_comment_count} 個")

    # 欠落している <tr> タグの自動補正
    # （元HTMLで </tr> の直後に <tr> を挟まず直接 <td> または <th> が書かれている箇所を補完）
    html_str = str(soup)
    tr_fix_pattern = r'(</tr>\s*)(<t[dh]\b)'
    fixed_count = len(re.findall(tr_fix_pattern, html_str))
    if fixed_count > 0:
        print(f"      -> 欠落していた <tr> 開始タグを自動補正: {fixed_count} 箇所")
        html_str = re.sub(tr_fix_pattern, r'\1<tr>\2', html_str)
        soup = BeautifulSoup(html_str, parser)

    # テーブルタグを検出
    table = soup.find("table")
    if not table:
        raise ValueError("HTML内に <table> タグが見つかりませんでした。")

    rows = table.find_all("tr")
    print(f"[3/5] テーブル解析中 (全 {len(rows)} 行)...")

    # ヘッダー情報の取得
    header_th = rows[0].find_all("th")
    orig_headers = [th.get_text(strip=True) for th in header_th]
    print(f"      元の列構成 ({len(orig_headers)}列): {orig_headers}")

    # テーブルグリッドを計算 (rowspan, colspan を正確に追跡)
    grid = {}
    cell_info = {}

    for r_idx, r in enumerate(rows):
        cells = r.find_all(["th", "td"], recursive=False)
        col = 0
        for cell in cells:
            while (r_idx, col) in grid:
                col += 1
            rs = int(cell.get("rowspan", 1))
            cs = int(cell.get("colspan", 1))
            cell_info[id(cell)] = {
                "cell": cell,
                "row": r_idx,
                "col": col,
                "rs": rs,
                "cs": cs
            }
            for dr in range(rs):
                for dc in range(cs):
                    grid[(r_idx + dr, col + dc)] = cell
            col += cs

    # 2. 先頭1列 (col == 0: マンション標準管理規約) のセルのみを厳密に削除
    # （行構造や他列のセル、コメント列は一切変更・削除しない）
    print("[4/5] 先頭1列（マンション標準管理規約）を削除し、2・3・4列目を保持...")
    deleted_cells = 0
    for r_idx, r in enumerate(rows):
        cells = r.find_all(["th", "td"], recursive=False)
        for cell in cells:
            info = cell_info.get(id(cell))
            if info and info["col"] == 0:
                cell.decompose()
                deleted_cells += 1

    # 3. ヘッダー幅の調整 (25% -> 33%)
    new_header_th = table.find_all("th")
    for th in new_header_th:
        if th.get("width") == "25%":
            th["width"] = col_width

    new_headers = [th.get_text(strip=True) for th in new_header_th]
    print(f"      変換後の列構成 ({len(new_headers)}列): {new_headers}")
    print(f"      -> 削除した先頭セル数: {deleted_cells} 個")

    # 4. 出力HTMLの組み立て
    print("[5/5] 出力HTMLを生成中...")
    if table_only:
        # テーブルタグのみ出力
        result_html = str(table)
    else:
        # メニュー (<nav>) の削除
        if soup.body:
            for nav in soup.body.find_all("nav"):
                nav.decompose()
            # table 外の見出し (h1〜h6) の削除
            for h in soup.body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                if not h.find_parent("table"):
                    h.decompose()

            # テーブルを囲む div.container-fluid があれば維持
            container = table.find_parent("div", class_="container-fluid")
            if not container:
                container = table.find_parent("div")

            target_elem = container if container else table
            soup.body.clear()
            soup.body.append(target_elem)

        # titleタグの調整
        if soup.title and soup.title.string:
            t = soup.title.string
            soup.title.string = t.replace("4col", "3col").replace("4列", "3列")

        soup_str = str(soup)
        if soup_str.strip().startswith("<!DOCTYPE html>"):
            result_html = soup_str
        else:
            result_html = "<!DOCTYPE html>\n" + soup_str

    # 出力ファイルに書き込み
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result_html)

    print("=" * 65)
    print(f"【生成完了】: {output_path}")
    print(f"  ・削除: 1列目（{orig_headers[0] if orig_headers else '先頭列'}）")
    print(f"  ・保持: 2列目（{orig_headers[1] if len(orig_headers)>1 else '2列目'}） -> 新1列目")
    print(f"  ・保持: 3列目（{orig_headers[2] if len(orig_headers)>2 else '3列目'}） -> 新2列目")
    print(f"  ・保持: 4列目（{orig_headers[3] if len(orig_headers)>3 else '4列目'}） -> 新3列目（コメント列）")
    print("=" * 65)
    return output_path

def main():
    parser = argparse.ArgumentParser(
        description="「kiyaku-taihi-4col.html」からメニュー・見出し・コメント・先頭1列を削除し、3列テーブルHTMLを生成するプログラム"
    )
    parser.add_argument("input_file", nargs="?", default=None, help="入力HTMLファイルパス（省略時は kiyaku/kiyaku-taihi-4col.html）")
    parser.add_argument("-o", "--output", dest="output_file", default=None, help="出力HTMLファイルパス（省略時は自動生成）")
    parser.add_argument("-t", "--table-only", action="store_true", help="HTMLヘッダー等を省き、tableタグのみ出力するモード")
    parser.add_argument("-w", "--width", dest="col_width", default="33%", help="ヘッダー列の幅指定（デフォルト: 33%）")

    args = parser.parse_args()

    input_file = args.input_file
    if not input_file:
        input_file = find_default_input()
        if not input_file:
            print("エラー: 入力ファイルが見つかりません。引数でファイルを指定してください。")
            print("使用例: python convert_kiyaku_3col.py kiyaku/kiyaku-taihi-4col.html")
            sys.exit(1)

    convert_4col_to_3col(
        input_path=input_file,
        output_path=args.output_file,
        table_only=args.table_only,
        col_width=args.col_width
    )

if __name__ == "__main__":
    main()
