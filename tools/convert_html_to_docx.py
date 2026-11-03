#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample.docx を参考にした規約対比表 HTML -> Microsoft Word (改正規約.docx) 変換プログラム
(convert_html_to_docx.py)

【仕様】
1. Release/kiyaku-taihi-3col.html から 3列の中央部分（改正案）のみを抽出
2. 出力ファイル: 改正規約.docx (カレントディレクトリおよび Release/ ディレクトリ)
3. 編集ルール:
   - ヘッダを「グランピア西白井（１ブロック）団地管理組合規約」とする
   - テーブルの1，2行をスキップし、3行目（第１章　総則）から開始する
   - 第1章を除き、章の前に空行を置き、その後ろの空行を削除する
   - 条見出しの先頭の半角スペース・全角スペースを除去する
   - セル内容が「（削除）」等の行はスキップし出力しない
   - 文字の配置、インデントは Sample.docx (ＭＳ 明朝 12pt, 各条項ぶら下げインデント) に従う
   - keep_with_next は設定しない（Word編集画面での「・」マーカー防止）
"""

import os
import sys
import shutil
import re
import argparse
from bs4 import BeautifulSoup
import docx
from docx.shared import Pt, Mm, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Windowsコンソールでの文字化け防止
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def set_run_font(run, font_name="ＭＳ 明朝", size_pt=12.0, bold=False, color_rgb=None):
    """Runにフォント名（日本語EastAsia対応）、サイズ、太字、色を設定"""
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.bold = bold
    if color_rgb:
        run.font.color.rgb = color_rgb
    
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn('w:eastAsia'), font_name)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)

def set_paragraph_indent(p, left_dxa=0, hanging_dxa=0, hanging_chars=0, left_chars=0, 
                         align=WD_PARAGRAPH_ALIGNMENT.LEFT):
    """
    Sample.docx に完全準拠した段落インデントと配置設定
    keep_with_next は一切設定しない（「・」マーカー防止）
    """
    p.alignment = align
    pf = p.paragraph_format
    
    # keep_with_next は設定しない
    pf.keep_with_next = False
    
    # spacing は設定しない（Word標準行グリッドに準拠）
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = None

    # ポイント換算 (1 dxa = 0.05 pt)
    if left_dxa > 0:
        pf.left_indent = Pt(left_dxa / 20.0)
    else:
        pf.left_indent = Pt(0)
        
    if hanging_dxa > 0:
        pf.first_line_indent = Pt(-hanging_dxa / 20.0)
    else:
        pf.first_line_indent = Pt(0)

    # OpenXML の w:ind に w:left, w:hanging, w:hangingChars, w:leftChars を明示設定
    if left_dxa > 0 or hanging_dxa > 0:
        pPr = p._p.get_or_add_pPr()
        ind = pPr.find(qn('w:ind'))
        if ind is None:
            ind = OxmlElement('w:ind')
            pPr.append(ind)
            
        if left_dxa > 0:
            ind.set(qn('w:left'), str(int(left_dxa)))
        if left_chars > 0:
            ind.set(qn('w:leftChars'), str(int(left_chars)))
        if hanging_dxa > 0:
            ind.set(qn('w:hanging'), str(int(hanging_dxa)))
        if hanging_chars > 0:
            ind.set(qn('w:hangingChars'), str(int(hanging_chars)))

def add_page_number_to_footer(footer):
    """フッターに中央揃えで - PAGE - フィールドを追加 (Sample.docx準拠)"""
    p = footer.paragraphs[0]
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    
    # ページ番号フィールド: - PAGE -
    run_pre = p.add_run("- ")
    set_run_font(run_pre, font_name="ＭＳ 明朝", size_pt=10.5, bold=False, color_rgb=RGBColor(100, 100, 100))
    
    fldSimple = OxmlElement('w:fldSimple')
    fldSimple.set(qn('w:instr'), 'PAGE   \\* MERGEFORMAT')
    p._p.append(fldSimple)
    
    run_post = p.add_run(" -")
    set_run_font(run_post, font_name="ＭＳ 明朝", size_pt=10.5, bold=False, color_rgb=RGBColor(100, 100, 100))

def extract_runs(element, current_styles=None):
    """要素内のテキストとインライン装飾を再帰的に抽出"""
    if current_styles is None:
        current_styles = {'bold': False, 'color': None}
    
    runs_data = []
    for child in element.children:
        if isinstance(child, str):
            text = str(child)
            # 改行コードのみを除去し、空白文字（全角スペース等）は完全保持
            text = text.replace('\r\n', '').replace('\n', '').replace('\r', '')
            if text:
                runs_data.append((text, current_styles.copy()))
        elif hasattr(child, 'name'):
            new_styles = current_styles.copy()
            if child.name in ['strong', 'b']:
                new_styles['bold'] = True
            classes = child.get('class', [])
            if 'fw-bold' in classes:
                new_styles['bold'] = True
            if 'tred' in classes:
                new_styles['color'] = RGBColor(255, 0, 0)
            el_id = child.get('id', '')
            # CSS: span[id^="sa"], span[id^="ga"], span[id^="na"], span[id^="nc"] など
            if any(el_id.startswith(p) for p in ['na', 'nc', 'sa', 'ga', 'sc', 'bc', 'fs', 'sph', 'gph']):
                new_styles['bold'] = True
            runs_data.extend(extract_runs(child, new_styles))
    return runs_data

def clean_heading_runs(runs):
    """見出しの場合、先頭と末尾の不要な空白（半角スペース、全角スペース、タブ、改行等）を除去"""
    if not runs:
        return runs
    # 先頭runのlstrip
    for idx in range(len(runs)):
        text, style = runs[idx]
        stripped = text.lstrip(' \t\u3000\r\n')
        if stripped != text:
            runs[idx] = (stripped, style)
        if stripped:
            break
    # 末尾runのrstrip
    for idx in range(len(runs) - 1, -1, -1):
        text, style = runs[idx]
        stripped = text.rstrip(' \t\u3000\r\n')
        if stripped != text:
            runs[idx] = (stripped, style)
        if stripped:
            break
    return [(t, s) for t, s in runs if t]

def is_deletion_cell(text):
    """セル内容が「（削除）」等の削除マーカーであるかを判定"""
    cleaned = text.strip().replace('>', '').replace('&gt;', '').strip()
    if cleaned in ['（削除）', '(削除)', '同上', '（該当しない）', '(該当しない)']:
        return True
    if re.match(r'^[（(]削除[）)]>?$', text.strip()):
        return True
    return False

def convert_html_to_docx(html_path, output_path):
    if not os.path.isfile(html_path):
        raise FileNotFoundError(f"入力ファイルが見つかりません: {html_path}")

    print("=" * 65)
    print("【規約対比表 HTML -> Microsoft Word (改正規約.docx) 変換】")
    print(f"入力HTML: {html_path}")
    print(f"出力Docx: {output_path}")
    print("=" * 65)

    print("[1/4] HTMLファイルを読み込み・解析中...")
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    table = soup.find("table")
    if not table:
        raise ValueError("HTML内に <table> タグが見つかりませんでした。")

    rows = table.find_all("tr")
    print(f"      テーブル総行数: {len(rows)} 行")

    print("[2/4] テーブルグリッド構造（rowspan/colspan）を展開中...")
    occupied = {}
    for r_idx, row in enumerate(rows):
        c_idx = 0
        cells = row.find_all(["th", "td"])
        for cell in cells:
            while (r_idx, c_idx) in occupied:
                c_idx += 1
            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))
            for dr in range(rowspan):
                for dc in range(colspan):
                    occupied[(r_idx + dr, c_idx + dc)] = (cell, dr == 0 and dc == 0)
            c_idx += colspan

    print("[3/4] Word文書を作成し、Sample.docx準拠のスタイルで出力中...")
    doc = docx.Document()

    # ページ設定（Sample.docx 準拠）
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(25.0)
    section.bottom_margin = Mm(20.0)
    section.left_margin = Mm(23.0)
    section.right_margin = Mm(23.0)

    # ヘッダー設定
    # 要件: ヘッダを「グランピア西白井（１ブロック）団地管理組合規約」とする
    header = section.header
    p_header = header.paragraphs[0]
    p_header.text = ""
    p_header.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    run_header = p_header.add_run("グランピア西白井（１ブロック）団地管理組合規約")
    set_run_font(run_header, font_name="ＭＳ 明朝", size_pt=9.0, bold=False, color_rgb=RGBColor(80, 80, 80))

    # フッター設定（ページ番号）
    add_page_number_to_footer(section.footer)

    processed_count = 0
    skipped_deletion_count = 0
    last_was_blank = False
    last_item_type = None
    is_first_chapter = True

    def add_blank_paragraph():
        p_blank = doc.add_paragraph()
        p_blank.paragraph_format.space_before = Pt(0)
        p_blank.paragraph_format.space_after = Pt(0)
        p_blank.paragraph_format.keep_with_next = False
        return p_blank

    # テーブルの1，2行をスキップし、3行目（r = 2：第１章　総則）から開始
    for r in range(2, len(rows)):
        cell_info = occupied.get((r, 1))
        if not cell_info:
            continue
        cell, is_origin = cell_info
        if not is_origin:
            continue

        cell_text = cell.get_text(strip=True)
        if not cell_text:
            continue

        # セル内容が「（削除）」等の行は出力しない
        if is_deletion_cell(cell_text):
            skipped_deletion_count += 1
            continue

        divs = cell.find_all("div")
        elements = divs if divs else [cell]

        row_classes = rows[r].get("class", [])
        cell_classes = cell.get("class", [])

        for el in elements:
            el_text = el.get_text(strip=True)
            if not el_text:
                continue

            # 要素内容が「（削除）」等の場合もスキップ
            if is_deletion_cell(el_text):
                skipped_deletion_count += 1
                continue

            el_classes = el.get("class", [])
            all_classes = set(el_classes + cell_classes)

            is_sho = "sho" in all_classes
            is_phs = "phs" in all_classes
            is_ttl = "ttl" in all_classes or "table-primary" in row_classes
            is_jou = "jou" in all_classes
            is_kou = "kou" in all_classes
            is_gou = "gou" in all_classes
            is_sai = "sai" in all_classes or "sais" in all_classes
            is_noind = "noind" in all_classes

            # 空行制御ロジック:
            # 1. 章 (.sho):
            #    第1章を除き、章の前に空行を置き、後ろの空行は置かない（削除）
            if is_sho:
                if is_first_chapter:
                    is_first_chapter = False
                else:
                    if not last_was_blank:
                        add_blank_paragraph()
                        last_was_blank = True

            # 2. 節 (.phs):
            #    直前が章でなければ節の前に空行を置く
            elif is_phs:
                if last_item_type != 'sho' and not last_was_blank:
                    add_blank_paragraph()
                    last_was_blank = True

            # 3. 条見出し (.ttl):
            #    直前が章または節でなければ、条見出しの前に空行を置く
            elif is_ttl:
                if last_item_type not in ('sho', 'phs') and not last_was_blank:
                    add_blank_paragraph()
                    last_was_blank = True

            # 新規段落作成
            p = doc.add_paragraph()

            # インデント設定（Sample.docx 準拠）
            # 1. 章 (.sho): 中央揃え、インデントなし
            if is_sho:
                set_paragraph_indent(p, left_dxa=0, hanging_dxa=0, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
                last_item_type = 'sho'
            # 2. 節 (.phs): 中央揃え、インデントなし
            elif is_phs:
                set_paragraph_indent(p, left_dxa=0, hanging_dxa=0, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
                last_item_type = 'phs'
            # 3. 条見出し (.ttl): 左揃え、インデントなし
            elif is_ttl:
                set_paragraph_indent(p, left_dxa=0, hanging_dxa=0, align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                last_item_type = 'ttl'
            # 4. 条 (.jou): left=480, hanging=480, hangingChars=200
            elif is_jou:
                set_paragraph_indent(p, left_dxa=480, hanging_dxa=480, hanging_chars=200, 
                                     align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                last_item_type = 'body'
            # 5. 項 (.kou): left=480, hanging=240, hangingChars=100, leftChars=200
            elif is_kou:
                set_paragraph_indent(p, left_dxa=480, hanging_dxa=240, hanging_chars=100, left_chars=200, 
                                     align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                last_item_type = 'body'
            # 6. 号 (.gou): left=960, hanging=480, hangingChars=200, leftChars=400
            elif is_gou:
                set_paragraph_indent(p, left_dxa=960, hanging_dxa=480, hanging_chars=200, left_chars=400, 
                                     align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                last_item_type = 'body'
            # 7. 細目 (.sai, .sais): left=1200, hanging=480, hangingChars=200, leftChars=500
            elif is_sai:
                set_paragraph_indent(p, left_dxa=1200, hanging_dxa=480, hanging_chars=200, left_chars=500, 
                                     align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                last_item_type = 'body'
            # 8. noind: left=240, hanging=240, hangingChars=100, leftChars=100
            elif is_noind:
                set_paragraph_indent(p, left_dxa=240, hanging_dxa=240, hanging_chars=100, left_chars=100, 
                                     align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                last_item_type = 'body'
            # 9. その他
            else:
                set_paragraph_indent(p, left_dxa=0, hanging_dxa=0, align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                last_item_type = 'body'

            # インライン要素抽出
            runs = extract_runs(el)

            # 見出し（章、節、条見出し）の場合、先頭と末尾の不要な空白（半角・全角）を除去
            if is_sho or is_phs or is_ttl:
                runs = clean_heading_runs(runs)

            for text, style in runs:
                r_bold = style.get('bold', False)
                r_color = style.get('color', None)
                run = p.add_run(text)
                set_run_font(run, font_name="ＭＳ 明朝", size_pt=12.0, bold=r_bold, color_rgb=r_color)

            processed_count += 1
            last_was_blank = False

    print(f"      除外した「（削除）」等のセル数: {skipped_deletion_count} 箇所")
    print(f"[4/4] 文書保存中... (全 {processed_count} 段落)")
    
    # 1. 指定パスへの保存
    try:
        doc.save(output_path)
        print(f"      出力完了: {output_path}")
    except PermissionError:
        alt_path = "改正規約(最新).docx"
        print(f"      [警告] {output_path} は他のアプリ（Word等）で開かれているため上書きできません。")
        print(f"      代替ファイルとして保存します: {alt_path}")
        doc.save(alt_path)

    # 2. Release ディレクトリへの保存/複製
    rel_dir = "Release"
    if os.path.isdir(rel_dir):
        rel_path = os.path.join(rel_dir, os.path.basename(output_path))
        try:
            doc.save(rel_path)
            print(f"      Release内に保存完了: {rel_path}")
        except PermissionError:
            print(f"      [警告] {rel_path} も開かれているため保存できませんでした。")

def main():
    parser = argparse.ArgumentParser(description="規約対比表 HTML から 改正規約.docx への変換")
    parser.add_argument("-i", "--input", default="Release/kiyaku-taihi-3col.html", help="入力HTMLファイルパス")
    parser.add_argument("-o", "--output", default="改正規約.docx", help="出力docxファイルパス")
    args = parser.parse_args()

    convert_html_to_docx(args.input, args.output)

if __name__ == "__main__":
    main()
