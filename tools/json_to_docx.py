#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理組合規約の JSON ファイル (.json) を Microsoft Word (.docx) 形式に変換するプログラム
(json_to_docx.py)

【仕様】
1. convert_html_to_docx.py (Sample.docx準拠) と同一のページ設定・フォント・段落インデント・空行ルールで出力
   - 用紙: A4縦 (210mm x 297mm), 余白: 上25mm / 下20mm / 左23mm / 右23mm
   - ヘッダー: 右揃え 9pt ＭＳ 明朝 (JSON内の bylaws_title を出力)
   - フッター: 中央揃え 10.5pt ＭＳ 明朝 (- PAGE -)
   - 本文フォント: ＭＳ 明朝 12pt
   - 段落インデント:
     * 章 (chapter): 中央揃え、インデントなし（第1章を除き直前に空行）
     * 節 (section): 中央揃え、インデントなし（直前が章でない場合は直前に空行）
     * 条見出し (title): 左揃え、インデントなし（直前が章・節でない場合は直前に空行）
     * 条・第1項: left=480, hanging=480, hangingChars=200（条番号は太字）
     * 項・第2項以降: left=480, hanging=240, hangingChars=100, leftChars=200（項番号は太字）
     * 号 (items): left=960, hanging=480, hangingChars=200, leftChars=400（号番号は太字）
     * 細目 (sub_items): left=1200, hanging=480, hangingChars=200, leftChars=500（細目番号は太字）
     * 詳細 (details): left=1200, hanging=480, hangingChars=200, leftChars=500
   - keep_with_next は設定しない（Word編集画面での「・」マーカー防止）

使い方:
    python json_to_docx.py [入力jsonファイル] [出力docxファイル]
    または
    python json_to_docx.py -i 管理組合規約.json -o 改正規約.docx
"""

import os
import sys
import json
import argparse
from pathlib import Path
import docx
from docx.shared import Pt, Mm, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Windowsコンソールでの文字化け防止
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HALF_TO_FULL_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")


def to_fullwidth_digits(n: int) -> str:
    """整数を全角数字文字列に変換する。"""
    return str(n).translate(HALF_TO_FULL_DIGITS)


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
    convert_html_to_docx.py (Sample.docx) に完全準拠した段落インデントと配置設定
    keep_with_next は一切設定しない（「・」マーカー防止）
    """
    p.alignment = align
    pf = p.paragraph_format

    pf.keep_with_next = False
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = None

    if left_dxa > 0:
        pf.left_indent = Pt(left_dxa / 20.0)
    else:
        pf.left_indent = Pt(0)

    if hanging_dxa > 0:
        pf.first_line_indent = Pt(-hanging_dxa / 20.0)
    else:
        pf.first_line_indent = Pt(0)

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
    """フッターに中央揃えで - PAGE - フィールドを追加 (convert_html_to_docx.py準拠)"""
    p = footer.paragraphs[0]
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)

    run_pre = p.add_run("- ")
    set_run_font(run_pre, font_name="ＭＳ 明朝", size_pt=10.5, bold=False, color_rgb=RGBColor(100, 100, 100))

    fldSimple = OxmlElement('w:fldSimple')
    fldSimple.set(qn('w:instr'), 'PAGE   \\* MERGEFORMAT')
    p._p.append(fldSimple)

    run_post = p.add_run(" -")
    set_run_font(run_post, font_name="ＭＳ 明朝", size_pt=10.5, bold=False, color_rgb=RGBColor(100, 100, 100))


def convert_json_to_docx(json_path, output_path):
    json_path = Path(json_path)
    output_path = Path(output_path)

    if not json_path.is_file():
        raise FileNotFoundError(f"入力JSONファイルが見つかりません: {json_path}")

    print("=" * 65)
    print("【管理組合規約 JSON -> Microsoft Word (.docx) 変換】")
    print(f"入力JSON: {json_path}")
    print(f"出力Docx: {output_path}")
    print("=" * 65)

    print("[1/3] JSONファイルを読み込み中...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    bylaws_title = data.get("bylaws_title") or "グランピア西白井（１ブロック）団地管理組合規約"
    chapters = data.get("chapters", [])
    print(f"      規約タイトル: {bylaws_title}")
    print(f"      章数: {len(chapters)} 章")

    print("[2/3] Word文書を作成し、convert_html_to_docx.py 準拠のスタイルで出力中...")
    doc = docx.Document()

    # ページ設定（convert_html_to_docx.py 準拠）
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(25.0)
    section.bottom_margin = Mm(20.0)
    section.left_margin = Mm(23.0)
    section.right_margin = Mm(23.0)

    # ヘッダー設定
    header = section.header
    p_header = header.paragraphs[0]
    p_header.text = ""
    p_header.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    run_header = p_header.add_run(bylaws_title)
    set_run_font(run_header, font_name="ＭＳ 明朝", size_pt=9.0, bold=False, color_rgb=RGBColor(80, 80, 80))

    # フッター設定（ページ番号）
    add_page_number_to_footer(section.footer)

    processed_count = 0
    article_count = 0
    last_was_blank = False
    last_item_type = None
    is_first_chapter = True

    def add_blank_paragraph():
        p_blank = doc.add_paragraph()
        p_blank.paragraph_format.space_before = Pt(0)
        p_blank.paragraph_format.space_after = Pt(0)
        p_blank.paragraph_format.keep_with_next = False
        return p_blank

    def add_styled_runs(p, runs_spec):
        """runs_spec: [(text, bold), ...] を段落に追加"""
        for text, is_bold in runs_spec:
            if text:
                r = p.add_run(text)
                set_run_font(r, font_name="ＭＳ 明朝", size_pt=12.0, bold=is_bold)

    for chapter in chapters:
        chap_num = (chapter.get("chapter_number") or "").strip()
        chap_title = (chapter.get("chapter_title") or "").strip()

        # 1. 章 (.sho)
        if chap_num or chap_title:
            if is_first_chapter:
                is_first_chapter = False
            else:
                if not last_was_blank:
                    add_blank_paragraph()
                    last_was_blank = True

            p_chap = doc.add_paragraph()
            set_paragraph_indent(p_chap, left_dxa=0, hanging_dxa=0, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
            chap_text = f"{chap_num}　{chap_title}" if (chap_num and chap_title) else (chap_num or chap_title)
            add_styled_runs(p_chap, [(chap_text, False)])
            processed_count += 1
            last_was_blank = False
            last_item_type = 'sho'

        for sec in chapter.get("sections", []):
            sec_num = (sec.get("section_number") or "").strip()
            sec_title = (sec.get("section_title") or "").strip()

            # 2. 節 (.phs)
            if sec_num or sec_title:
                if last_item_type != 'sho' and not last_was_blank:
                    add_blank_paragraph()
                    last_was_blank = True

                p_sec = doc.add_paragraph()
                set_paragraph_indent(p_sec, left_dxa=0, hanging_dxa=0, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
                sec_text = f"{sec_num}　{sec_title}" if (sec_num and sec_title) else (sec_num or sec_title)
                add_styled_runs(p_sec, [(sec_text, False)])
                processed_count += 1
                last_was_blank = False
                last_item_type = 'phs'

            for article in sec.get("articles", []):
                article_count += 1
                art_num = (article.get("article_number") or "").strip()
                art_title = (article.get("title") or "").strip()

                # 3. 条見出し (.ttl)
                if art_title:
                    if last_item_type not in ('sho', 'phs') and not last_was_blank:
                        add_blank_paragraph()
                        last_was_blank = True

                    p_ttl = doc.add_paragraph()
                    set_paragraph_indent(p_ttl, left_dxa=0, hanging_dxa=0, align=WD_PARAGRAPH_ALIGNMENT.LEFT)
                    if not (art_title.startswith("（") and art_title.endswith("）")):
                        ttl_text = f"（{art_title}）"
                    else:
                        ttl_text = art_title
                    add_styled_runs(p_ttl, [(ttl_text, False)])
                    processed_count += 1
                    last_was_blank = False
                    last_item_type = 'ttl'
                else:
                    # 条見出しが無い場合でも、直前が章・節でなければ条の前に空行を置く
                    if last_item_type not in ('sho', 'phs') and not last_was_blank:
                        add_blank_paragraph()
                        last_was_blank = True

                # 4. 各項 (paragraphs)
                for p_idx, para in enumerate(article.get("paragraphs", [])):
                    para_no = para.get("paragraph_no", p_idx + 1)
                    para_text = (para.get("text") or "").strip()

                    p_para = doc.add_paragraph()
                    if para_no == 1 and p_idx == 0:
                        # 条 (.jou): left=480, hanging=480, hangingChars=200
                        set_paragraph_indent(
                            p_para, left_dxa=480, hanging_dxa=480, hanging_chars=200,
                            align=WD_PARAGRAPH_ALIGNMENT.LEFT
                        )
                        if art_num:
                            add_styled_runs(p_para, [(art_num, True), (f"　{para_text}", False)])
                        else:
                            add_styled_runs(p_para, [(para_text, False)])
                    else:
                        # 項 (.kou): left=480, hanging=240, hangingChars=100, leftChars=200
                        set_paragraph_indent(
                            p_para, left_dxa=480, hanging_dxa=240, hanging_chars=100, left_chars=200,
                            align=WD_PARAGRAPH_ALIGNMENT.LEFT
                        )
                        para_no_str = to_fullwidth_digits(para_no) if int(para_no) < 10 else str(para_no)
                        add_styled_runs(p_para, [(f"{para_no_str}　", True), (para_text, False)])

                    processed_count += 1
                    last_was_blank = False
                    last_item_type = 'body'

                    # 5. 各号 (items)
                    for item in para.get("items", []):
                        item_no = (item.get("item_no") or "").strip()
                        p_item = doc.add_paragraph()
                        # 号 (.gou): left=960, hanging=480, hangingChars=200, leftChars=400
                        set_paragraph_indent(
                            p_item, left_dxa=960, hanging_dxa=480, hanging_chars=200, left_chars=400,
                            align=WD_PARAGRAPH_ALIGNMENT.LEFT
                        )

                        if "term" in item and "definition" in item:
                            term = (item.get("term") or "").strip()
                            definition = (item.get("definition") or "").strip()
                            item_body = f"　{term}　{definition}"
                        else:
                            raw_item_text = (item.get("text") or "").strip()
                            # docx_to_json.py で正規化された半角スペース（施設名・役職名と対象者の区切り）を全角スペースに復元
                            item_body = f"　{raw_item_text.replace(' ', '　')}"

                        add_styled_runs(p_item, [(item_no, True), (item_body, False)])
                        processed_count += 1
                        last_was_blank = False
                        last_item_type = 'body'

                        # 6. 号の細目 (sub_items: イ, ロ, ①, ② など)
                        for sub in item.get("sub_items", []):
                            sub_no = (sub.get("sub_item_no") or "").strip()
                            sub_text = (sub.get("text") or "").strip()
                            p_sub = doc.add_paragraph()
                            # 細目 (.sai): left=1200, hanging=480, hangingChars=200, leftChars=500
                            set_paragraph_indent(
                                p_sub, left_dxa=1200, hanging_dxa=480, hanging_chars=200, left_chars=500,
                                align=WD_PARAGRAPH_ALIGNMENT.LEFT
                            )
                            add_styled_runs(p_sub, [(sub_no, True), (f"　{sub_text}", False)])
                            processed_count += 1
                            last_was_blank = False
                            last_item_type = 'body'

                            # 7. 細目の詳細 (details: （１）, （２） など)
                            for det in sub.get("details", []):
                                det_no = (det.get("detail_no") or "").strip()
                                det_text = (det.get("text") or "").strip()
                                p_det = doc.add_paragraph()
                                set_paragraph_indent(
                                    p_det, left_dxa=1200, hanging_dxa=480, hanging_chars=200, left_chars=500,
                                    align=WD_PARAGRAPH_ALIGNMENT.LEFT
                                )
                                add_styled_runs(p_det, [(f"{det_no}{det_text}", False)])
                                processed_count += 1
                                last_was_blank = False
                                last_item_type = 'body'

    print(f"[3/3] 文書保存中... (全 {len(chapters)} 章 / {article_count} 条 / {processed_count} 段落)")
    try:
        doc.save(str(output_path))
        print(f"      出力完了: {output_path}")
    except PermissionError:
        alt_path = output_path.with_name(f"{output_path.stem}(最新){output_path.suffix}")
        print(f"      [警告] {output_path} は他のアプリ（Word等）で開かれているため上書きできません。")
        print(f"      代替ファイルとして保存します: {alt_path}")
        doc.save(str(alt_path))

    return data


def main():
    parser = argparse.ArgumentParser(
        description="管理組合規約 JSON ファイル (.json) から Microsoft Word (.docx) への変換"
    )
    parser.add_argument("pos_input", nargs="?", default=None, help="入力JSONファイルパス（位置引数）")
    parser.add_argument("pos_output", nargs="?", default=None, help="出力docxファイルパス（位置引数）")
    parser.add_argument("-i", "--input", dest="opt_input", default=None, help="入力JSONファイルパス")
    parser.add_argument("-o", "--output", dest="opt_output", default=None, help="出力docxファイルパス")
    args = parser.parse_args()

    input_str = args.opt_input or args.pos_input or "管理組合規約.json"
    input_path = Path(input_str)

    output_str = args.opt_output or args.pos_output
    if output_str:
        output_path = Path(output_str)
    else:
        output_path = input_path.with_suffix(".docx")

    if not input_path.is_file():
        print(f"エラー: 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    convert_json_to_docx(input_path, output_path)


if __name__ == "__main__":
    main()
