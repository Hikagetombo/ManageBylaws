#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理組合規約の Word ファイル (.docx) を JSON 形式に変換するスクリプト。

使い方:
    python docx_to_json.py [入力docxファイル] [出力jsonファイル]

引数を省略した場合、同じディレクトリ内の
「1ブロック規約（2013年）.docx」を読み込み、
「1ブロック規約（2013年）.json」を出力します。
"""

import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

# 半角数字 -> 全角数字の変換テーブル
HALF_TO_FULL_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")
# 全角数字 -> 半角数字の変換テーブル
FULL_TO_HALF_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

KANJI_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def parse_number(s: str) -> int:
    """全角・半角・漢数字を整数に変換する。"""
    s_half = s.translate(FULL_TO_HALF_DIGITS)
    if s_half.isdigit():
        return int(s_half)
    if s in KANJI_DIGITS:
        return KANJI_DIGITS[s]
    if s.startswith("十"):
        return 10 + KANJI_DIGITS.get(s[1:], 0)
    if "十" in s:
        parts = s.split("十")
        tens = KANJI_DIGITS.get(parts[0], 1)
        ones = KANJI_DIGITS.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    raise ValueError(f"数値に変換できません: {s}")


def to_fullwidth_digits(n: int) -> str:
    """整数を全角数字文字列に変換する。"""
    return str(n).translate(HALF_TO_FULL_DIGITS)


def normalize_spaces(text: str) -> str:
    """連続する空白（全角・半角スペース）を単一の半角スペースに正規化し、前後をトリムする。"""
    return re.sub(r"[\s　]+", " ", text).strip()


def load_numbering_map(zf: zipfile.ZipFile) -> dict[tuple[str, str], tuple[int, str]]:
    """
    word/numbering.xml を解析し、(numId, ilvl) -> (開始番号, lvlText) の辞書を返す。
    Word の自動段落番号（w:numPr）が付与されている段落の番号復元に使用する。
    """
    if "word/numbering.xml" not in zf.namelist():
        return {}

    xml_bytes = zf.read("word/numbering.xml")
    root = ET.fromstring(xml_bytes)

    abstract_map: dict[str, dict[str, tuple[int, str]]] = {}
    for abs_num in root.findall("w:abstractNum", NS):
        abs_id = abs_num.get(f"{{{W_NS}}}abstractNumId")
        if abs_id is None:
            continue
        lvl_dict: dict[str, tuple[int, str]] = {}
        for lvl in abs_num.findall("w:lvl", NS):
            ilvl = lvl.get(f"{{{W_NS}}}ilvl", "0")
            start_el = lvl.find("w:start", NS)
            lvl_text_el = lvl.find("w:lvlText", NS)
            start_val = int(start_el.get(f"{{{W_NS}}}val", "1")) if start_el is not None else 1
            lvl_text = lvl_text_el.get(f"{{{W_NS}}}val", "%1") if lvl_text_el is not None else "%1"
            lvl_dict[ilvl] = (start_val, lvl_text)
        abstract_map[abs_id] = lvl_dict

    num_map: dict[tuple[str, str], tuple[int, str]] = {}
    for num in root.findall("w:num", NS):
        num_id = num.get(f"{{{W_NS}}}numId")
        abs_id_el = num.find("w:abstractNumId", NS)
        if num_id is None or abs_id_el is None:
            continue
        abs_id = abs_id_el.get(f"{{{W_NS}}}val")
        if abs_id not in abstract_map:
            continue
        for ilvl, (start_val, lvl_text) in abstract_map[abs_id].items():
            num_map[(num_id, ilvl)] = (start_val, lvl_text)

        # startOverride がある場合は上書き
        for override in num.findall("w:lvlOverride", NS):
            ilvl = override.get(f"{{{W_NS}}}ilvl", "0")
            start_ovr = override.find("w:startOverride", NS)
            if start_ovr is not None and (num_id, ilvl) in num_map:
                ovr_val = int(start_ovr.get(f"{{{W_NS}}}val", "1"))
                _, lvl_text = num_map[(num_id, ilvl)]
                num_map[(num_id, ilvl)] = (ovr_val, lvl_text)

    return num_map


def extract_paragraphs_from_docx(docx_path: Path) -> list[str]:
    """
    .docx ファイル内の word/document.xml から段落テキストのリストを抽出する。
    自動番号 (w:numPr) が設定されている場合は番号文字列を先頭に補完する。
    """
    with zipfile.ZipFile(docx_path, "r") as zf:
        num_map = load_numbering_map(zf)
        num_counters: dict[tuple[str, str], int] = {}

        xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)

    body = root.find("w:body", NS)
    if body is None:
        return []

    paragraphs: list[str] = []
    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            p_elements = [child]
        elif tag == "tbl":
            p_elements = child.findall(".//w:p", NS)
        else:
            continue

        for p_el in p_elements:
            texts = [t.text for t in p_el.findall(".//w:t", NS) if t.text]
            line = "".join(texts).strip()
            if not line:
                continue

            # 自動段落番号 (w:numPr) の確認
            num_pr = p_el.find(".//w:pPr/w:numPr", NS)
            if num_pr is not None:
                num_id_el = num_pr.find("w:numId", NS)
                ilvl_el = num_pr.find("w:ilvl", NS)
                num_id = num_id_el.get(f"{{{W_NS}}}val") if num_id_el is not None else None
                ilvl = ilvl_el.get(f"{{{W_NS}}}val", "0") if ilvl_el is not None else "0"
                if num_id and (num_id, ilvl) in num_map:
                    start_val, lvl_text = num_map[(num_id, ilvl)]
                    current_val = num_counters.get((num_id, ilvl), start_val)
                    num_counters[(num_id, ilvl)] = current_val + 1
                    prefix = lvl_text.replace(f"%{int(ilvl) + 1}", str(current_val))
                    if not line.startswith(prefix):
                        line = f"{prefix}　{line}"

            paragraphs.append(line)

    return paragraphs


def parse_bylaws_paragraphs(
    paragraphs: list[str],
    default_title: str = "グランピア西白井（１ブロック）団地管理組合規約",
) -> dict:
    """段落リストを解析し、規約 JSON 構造の辞書を生成する。"""
    bylaws_title = default_title
    chapters: list[dict] = []

    current_chapter: dict | None = None
    current_section: dict | None = None
    current_article: dict | None = None
    current_paragraph: dict | None = None
    current_item: dict | None = None
    current_sub_item: dict | None = None

    pending_article_title: str | None = None

    # 正規表現パターン
    re_supplementary = re.compile(r"^(?:附[\s　]*則|別[\s　]*表)")
    re_chapter = re.compile(r"^第([０-９0-9一二三四五六七八九十]+)章[\s　]+(.+)$")
    re_section = re.compile(r"^第([０-９0-9一二三四五六七八九十]+)節[\s　]+(.+)$")
    re_art_title = re.compile(r"^[（\(]([^）\)]+)[）\)]$")
    re_article = re.compile(
        r"^第([０-９0-9一二三四五六七八九十]+)条(?:の([０-９0-9一二三四五六七八九十]+))?[\s　]+(.*)$"
    )
    re_paragraph = re.compile(r"^([０-９0-9]+)[\s　]+(.+)$")
    re_item = re.compile(r"^([一二三四五六七八九十百ニ]+)(?:[\s　]+(.+))?$")
    re_sub_item_circle = re.compile(r"^([①-⑳])[\s　]*(.+)$")
    re_sub_item_kana = re.compile(r"^([イロハニホヘト])[\s　]+(.+)$")
    re_detail = re.compile(r"^([（\(][０-９0-9]+[）\)])[\s　]*(.+)$")

    for raw_line in paragraphs:
        line = raw_line.strip()
        if not line:
            continue

        # 附則・別表に到達したら本則の解析を終了する
        if re_supplementary.match(line):
            break

        # 1. 章 (第X章 ...)
        m_chap = re_chapter.match(line)
        if m_chap:
            chap_num_int = parse_number(m_chap.group(1))
            chap_num_str = f"第{to_fullwidth_digits(chap_num_int)}章"
            chap_title = re.sub(r"[\s　]+", "", m_chap.group(2))
            current_chapter = {
                "chapter_number": chap_num_str,
                "chapter_title": chap_title,
                "sections": [],
            }
            chapters.append(current_chapter)
            current_section = None
            current_article = None
            current_paragraph = None
            current_item = None
            current_sub_item = None
            pending_article_title = None
            continue

        # 第1章が始まる前のテキストは規約タイトルとして扱う
        if current_chapter is None:
            bylaws_title = normalize_spaces(line)
            continue

        # 2. 節 (第X節 ...)
        m_sec = re_section.match(line)
        if m_sec:
            sec_num_int = parse_number(m_sec.group(1))
            sec_num_str = f"第{to_fullwidth_digits(sec_num_int)}節"
            sec_title = re.sub(r"[\s　]+", "", m_sec.group(2))
            current_section = {
                "section_number": sec_num_str,
                "section_title": sec_title,
                "articles": [],
            }
            current_chapter["sections"].append(current_section)
            current_article = None
            current_paragraph = None
            current_item = None
            current_sub_item = None
            pending_article_title = None
            continue

        # 3. 条見出し ((目的) / （目的）)
        m_title = re_art_title.match(line)
        if m_title and current_sub_item is None:
            # ただし（１）のような細分番号は除外
            inner = m_title.group(1).strip()
            if not inner.translate(FULL_TO_HALF_DIGITS).isdigit():
                pending_article_title = inner
                continue

        # 4. 条 (第X条 / 第X条のY ...)
        m_art = re_article.match(line)
        if m_art:
            main_num = parse_number(m_art.group(1))
            sub_raw = m_art.group(2)
            body_text = normalize_spaces(m_art.group(3))

            if main_num < 10:
                art_num_str = f"第{to_fullwidth_digits(main_num)}条"
            else:
                art_num_str = f"第{main_num}条"

            if sub_raw:
                sub_num = parse_number(sub_raw)
                art_id = f"art_{main_num:04d}_{sub_num:02d}"
                art_num_str += f"の{to_fullwidth_digits(sub_num)}"
            else:
                art_id = f"art_{main_num:04d}"

            if current_section is None:
                current_section = {
                    "section_number": None,
                    "section_title": None,
                    "articles": [],
                }
                current_chapter["sections"].append(current_section)

            current_paragraph = {
                "paragraph_no": 1,
                "text": body_text,
                "items": [],
            }
            current_article = {
                "article_id": art_id,
                "article_number": art_num_str,
                "title": pending_article_title or "",
                "paragraphs": [current_paragraph],
            }
            current_section["articles"].append(current_article)
            pending_article_title = None
            current_item = None
            current_sub_item = None
            continue

        # 5. 項 (２ ... / 10 ...)
        m_para = re_paragraph.match(line)
        if m_para and current_article is not None:
            para_no = parse_number(m_para.group(1))
            para_text = normalize_spaces(m_para.group(2))
            current_paragraph = {
                "paragraph_no": para_no,
                "text": para_text,
                "items": [],
            }
            current_article["paragraphs"].append(current_paragraph)
            current_item = None
            current_sub_item = None
            continue

        # 6. 号の細分 detail (（１）... / （２）...)
        m_detail = re_detail.match(line)
        if m_detail and current_sub_item is not None:
            detail_no = m_detail.group(1)
            detail_text = normalize_spaces(m_detail.group(2))
            if "details" not in current_sub_item:
                current_sub_item["details"] = []
            current_sub_item["details"].append({
                "detail_no": detail_no,
                "text": detail_text,
            })
            continue

        # 7. 号の細分 sub_item (①... / イ ...)
        # カタカナの「ニ」は、既に イ・ロ・ハ 等の sub_items が存在する場合のみ細分として扱い、
        # それ以外（「一」の直後など）は漢数字「二」の誤記（号）として扱う
        m_sub_circle = re_sub_item_circle.match(line)
        m_sub_kana = re_sub_item_kana.match(line)
        is_valid_kana_sub = (
            m_sub_kana is not None
            and (m_sub_kana.group(1) == "イ" or (current_item is not None and "sub_items" in current_item))
        )
        m_sub = m_sub_circle or (m_sub_kana if is_valid_kana_sub else None)
        if m_sub and current_item is not None:
            sub_no = m_sub.group(1)
            sub_text = normalize_spaces(m_sub.group(2))
            if "sub_items" not in current_item:
                current_item["sub_items"] = []
            current_sub_item = {
                "sub_item_no": sub_no,
                "text": sub_text,
            }
            current_item["sub_items"].append(current_sub_item)
            continue

        # 8. 号 (一 ... / 二 ... / 十一 ...)
        m_item = re_item.match(line)
        if m_item and current_paragraph is not None:
            # カタカナの「ニ」が漢数字の「二」として使われている場合を正規化
            item_no = m_item.group(1).replace("ニ", "二")
            item_text = normalize_spaces(m_item.group(2) or "")
            current_item = {
                "item_no": item_no,
                "text": item_text,
            }
            current_paragraph["items"].append(current_item)
            current_sub_item = None
            continue

        # 9. 継続行（Word上で段落分けされた折り返し行）の結合
        cont_text = normalize_spaces(line)
        if current_sub_item is not None:
            if current_sub_item.get("details"):
                current_sub_item["details"][-1]["text"] += cont_text
            else:
                current_sub_item["text"] += cont_text
        elif current_item is not None:
            # 第16条第一号のように施設名と使用者名が改行で分かれている場合はスペースを補う
            if (
                current_article
                and current_article["article_number"] == "第16条"
                and current_item["item_no"] == "一"
                and current_item["text"]
            ):
                current_item["text"] += " " + cont_text
            else:
                current_item["text"] += cont_text
        elif current_paragraph is not None:
            current_paragraph["text"] += cont_text

    # 後処理: 第2条（定義）の各号を term / definition に分割
    for chapter in chapters:
        for section in chapter["sections"]:
            for article in section["articles"]:
                if article["article_number"] == "第２条" and article["title"] == "定義":
                    for para in article["paragraphs"]:
                        new_items = []
                        for item in para["items"]:
                            raw_text = item.get("text", "")
                            term = None
                            definition = None

                            # パターン1: 「〇〇とは、△△」（1ブロック規約（2013年）.docx 形式）
                            if "とは、" in raw_text:
                                term, definition = raw_text.split("とは、", 1)
                            else:
                                # パターン2: 「〇〇 △△」（規約改正案.docx 形式）
                                parts = raw_text.split(" ", 1)
                                if len(parts) == 2:
                                    term, definition = parts[0], parts[1]

                            if term is not None and definition is not None:
                                new_item: dict = {
                                    "item_no": item["item_no"],
                                    "term": term.strip(),
                                    "definition": definition.strip(),
                                }
                                if "sub_items" in item:
                                    new_item["sub_items"] = item["sub_items"]
                                new_items.append(new_item)
                            else:
                                new_items.append(item)
                        para["items"] = new_items

    return {
        "bylaws_title": bylaws_title,
        "chapters": chapters,
    }


def convert_docx_to_json(input_docx: Path, output_json: Path) -> dict:
    """指定された .docx ファイルを読み込み、JSON ファイルへ書き出す。"""
    paragraphs = extract_paragraphs_from_docx(input_docx)
    data = parse_bylaws_paragraphs(paragraphs)
    output_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return data


def main() -> None:
    base_dir = Path(__file__).resolve().parent

    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1])
    else:
        input_path = base_dir / "1ブロック規約（2013年）.docx"

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_suffix(".json")

    if not input_path.exists():
        print(f"エラー: 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    data = convert_docx_to_json(input_path, output_path)
    total_articles = sum(
        len(sec["articles"])
        for chap in data["chapters"]
        for sec in chap["sections"]
    )
    print(f"変換完了: {input_path.name} -> {output_path.name}")
    print(f"章数: {len(data['chapters'])}, 条数: {total_articles}")


if __name__ == "__main__":
    main()
