#!usrbinenv python3

format_index.py

extract_index.py が出力した index.txt  index_merged.txt（単語・読み・ページ数・ファイル名の
タブ区切り）を読み込み、aws_index.txt のような

  ■■■記号・数字（数字・記号始まり・分類不能な語をまとめて格納）
  ■■■英字
    ■■A
    ■■B ...
    ■■Z
  ■■■かな
    ■■あ
    ■■い
    ■■う ... ■■ん（46音、1文字ずつ）

の見出し構成に自動グルーピングし、各グループ内をソートして出力する。
複数ファイルにまたがって出現する同一語は、ページ番号をまとめて重複排除する。

濁音・半濁音・拗音・促音・長音は、見出し上は対応する清音の1文字に畳み込む
（例 「が」→「か」の見出し、「ぎゃ」→「き」の見出し）。
記号のみ・断片的なハイライトなど、A〜Zあ〜んに分類できない語は
「記号・数字」セクションにまとめて出力する（削除はしない）。

使い方
  python format_index.py index.txt
  python format_index.py index_merged.txt -o final_index.txt

依存パッケージ
  pip install pykakasi


import argparse
import csv
import re
import sys
from pathlib import Path

# 見出しに使う46音（濁音・半濁音・拗音・促音・長音はここに畳み込まれる）
KANA_ORDER = list(
    あいうえお
    かきくけこ
    さしすせそ
    たちつてと
    なにぬねの
    はひふへほ
    まみむめも
    やゆよ
    らりるれろ
    わをん
)

# 濁音・半濁音 → 清音への畳み込み
_VOICED_TO_SEION = {
    が か, ぎ き, ぐ く, げ け, ご こ,
    ざ さ, じ し, ず す, ぜ せ, ぞ そ,
    だ た, ぢ ち, づ つ, で て, ど と,
    ば は, び ひ, ぶ ふ, べ へ, ぼ ほ,
    ぱ は, ぴ ひ, ぷ ふ, ぺ へ, ぽ ほ,
}
# 拗音・促音などの小書き文字 → 該当する大文字への畳み込み
_SMALL_TO_BASE = {
    ぁ あ, ぃ い, ぅ う, ぇ え, ぉ お,
    ゃ や, ゅ ゆ, ょ よ, っ つ, ゎ わ,
}


def normalize_mora(c str) - str
    濁音・拗音などを見出し用の46音のいずれかに畳み込む
    c = _VOICED_TO_SEION.get(c, c)
    c = _SMALL_TO_BASE.get(c, c)
    return c


def kata_to_hira(s str) - str
    カタカナをひらがなに変換する（長音記号ーなどはそのまま）
    result = []
    for ch in s
        code = ord(ch)
        if 0x30A1 = code = 0x30F6
            result.append(chr(code - 0x60))
        else
            result.append(ch)
    return .join(result)


def natural_key(s str)
    数字を数値として比較する自然順ソート用キー
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r(d+), s)]


def classify(term str, yomi str)
    
    語を (セクション, サブ見出し, ソートキー) に分類する。
    セクション 記号数字  英字  かな
    サブ見出し 英字なら A〜Z、かなならKANA_ORDER中の1文字、記号数字ならNone
    
    if not term
        return (記号数字, None, term)

    first = term[0]

    if first.isascii() and first.isalpha()
        return (英字, first.upper(), term.lower())

    hira = kata_to_hira(yomi or term)
    first_hira = normalize_mora(hira[0]) if hira else 
    if first_hira in KANA_ORDER
        return (かな, first_hira, hira)

    # 数字始まり・記号のみ・分類できなかった語はすべてここにまとめる
    return (記号数字, None, natural_key(term))


def merge_pages(pages)
    ページ番号の集合を数値順・重複排除して「、」区切りにまとめる
    numeric = sorted({int(p) for p in pages if str(p).isdigit()})
    non_numeric = sorted({str(p) for p in pages if not str(p).isdigit()})
    parts = [str(n) for n in numeric] + non_numeric
    return 、.join(parts)


def load_entries(input_path Path)
    タブ区切りの索引ファイルを読み込み、語ごとにページ番号を集約する
    merged = {}  # term - {yomi str, pages set}

    with open(input_path, r, encoding=utf-8-sig, newline=) as f
        reader = csv.DictReader(f, delimiter=t)
        for row in reader
            term = (row.get(単語) or ).strip()
            yomi = (row.get(読み) or ).strip()
            pages_raw = (row.get(ページ数) or ).strip()
            if not term
                continue

            # すでに「、」や「, 」でまとめられている場合にも対応
            page_list = re.split(r[、,]s, pages_raw) if pages_raw else []

            entry = merged.setdefault(term, {yomi yomi, pages set()})
            if yomi and not entry[yomi]
                entry[yomi] = yomi
            entry[pages].update(p for p in page_list if p)

    return merged


def build_sections(merged dict)
    sections = {記号数字 [], 英字 {}, かな {}}

    for term, data in merged.items()
        section, sub, sort_key = classify(term, data[yomi])
        pages_str = merge_pages(data[pages])

        if section == 記号数字
            sections[記号数字].append((sort_key, term, pages_str))
        elif section == 英字
            sections[英字].setdefault(sub, []).append((sort_key, term, pages_str))
        else
            sections[かな].setdefault(sub, []).append((sort_key, term, pages_str))

    sections[記号数字].sort(key=lambda x x[0])
    for sub in sections[英字]
        sections[英字][sub].sort(key=lambda x x[0])
    for sub in sections[かな]
        sections[かな][sub].sort(key=lambda x x[0])

    return sections


def write_output(sections dict, out_path Path)
    lines = [■■■索引]

    if sections[記号数字]
        lines.append(■■記号・数字（数字・記号始まり・分類不能な語をまとめて格納）)
        for _, term, pages in sections[記号数字]
            lines.append(f{term}t{pages})
        lines.append()

    for letter in sorted(sections[英字].keys())
        lines.append(f■■{letter})
        for _, term, pages in sections[英字][letter]
            lines.append(f{term}t{pages})
        lines.append()

    for mora in KANA_ORDER
        if mora not in sections[かな]
            continue
        lines.append(f■■{mora})
        for _, term, pages in sections[かな][mora]
            lines.append(f{term}t{pages})
        lines.append()

    with open(out_path, w, encoding=utf-8-sig) as f
        f.write(n.join(lines).rstrip() + n)


def main()
    parser = argparse.ArgumentParser(description=索引をグルーピング・ソートして整形する)
    parser.add_argument(input_path, help=extract_index.py が出力したタブ区切りファイル)
    parser.add_argument(-o, --output, help=出力ファイルパス(省略時は入力名+_formatted.txt))
    args = parser.parse_args()

    input_path = Path(args.input_path)
    if not input_path.exists()
        print(fエラー ファイルが見つかりません {input_path}, file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output) if args.output else input_path.with_name(
        input_path.stem + _formatted.txt
    )

    merged = load_entries(input_path)
    sections = build_sections(merged)
    write_output(sections, out_path)

    total = sum(len(v) if isinstance(v, list) else sum(len(vv) for vv in v.values())
                for v in sections.values())
    n_headings = len(sections[英字]) + len(sections[かな]) + (1 if sections[記号数字] else 0)
    print(f完了 {out_path})
    print(f合計 {total}件  見出し数 {n_headings})


if __name__ == __main__
    main()