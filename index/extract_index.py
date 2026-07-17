import fitz  # PyMuPDF（ハイライト検出用）
import pdfplumber  # テキスト抽出用
import pandas as pd
from pykakasi import kakasi
import os
import glob
import sys
import re

# ==========================================
# 設定エリア
# ==========================================
OUTPUT_FILE = "index.txt"
OUTPUT_FILE_MERGED = "index_merged.txt"
FOOTER_RATIO = 0.1
MERGE_DUPLICATES = True
USE_PDFPLUMBER = True  # pdfplumberを使うか
# ==========================================

def get_reading(text):
    """pykakasiを使って読み仮名（カタカナ）を取得"""
    kks = kakasi()
    result = kks.convert(text)
    reading = ""
    for item in result:
        reading += item['kana']
    return reading

def get_footer_number(page, is_left_half):
    """
    指定された位置（左下 or 右下）からノンブル（数字）を読み取る関数
    """
    r = page.rect
    h = r.height
    w = r.width
    
    footer_top = h * (1.0 - FOOTER_RATIO)
    
    if is_left_half:
        clip_rect = fitz.Rect(0, footer_top, w / 2, h)
    else:
        clip_rect = fitz.Rect(w / 2, footer_top, w, h)
    
    footer_text = page.get_text("text", clip=clip_rect).strip()
    match = re.search(r'(\d+)', footer_text)
    
    if match:
        return match.group(1)
    else:
        return "不明"

def extract_text_from_rect_pdfplumber(plumber_page, rect, page_height):
    """
    pdfplumberを使って指定領域からテキストを抽出
    PyMuPDFの座標系（左上原点）をpdfplumberの座標系（左下原点）に変換
    """
    # 座標変換: PyMuPDF (y0が上) → pdfplumber (y0が下)
    bbox = (
        rect.x0,
        page_height - rect.y1,  # 上下反転
        rect.x1,
        page_height - rect.y0   # 上下反転
    )
    
    # 指定領域のテキストを抽出
    cropped = plumber_page.within_bbox(bbox)
    text = cropped.extract_text()
    
    return text.strip().replace('\n', ' ') if text else ""

def extract_text_from_rect_pymupdf(page, rect):
    """
    PyMuPDFで複数の方法を試してテキスト抽出
    """
    # 方法1: 通常のテキスト抽出
    text1 = page.get_text("text", clip=rect).strip().replace('\n', ' ')
    
    # 方法2: dict形式
    blocks = page.get_text("dict", clip=rect)
    text2_parts = []
    for block in blocks.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text2_parts.append(span.get("text", ""))
    text2 = " ".join(text2_parts).strip()
    
    # より長いテキストを採用
    return text1 if len(text1) >= len(text2) else text2

def process_pdf(pdf_path, data_list):
    filename = os.path.basename(pdf_path)
    print(f"  > 読み込み中: {filename}")
    
    try:
        # PyMuPDFでハイライト情報を取得
        fitz_doc = fitz.open(pdf_path)
        
        # pdfplumberでテキスト抽出（オプション）
        if USE_PDFPLUMBER:
            import pdfplumber
            plumber_doc = pdfplumber.open(pdf_path)
        
    except Exception as e:
        print(f"    エラー: 開けませんでした ({e})")
        return

    for page_index, fitz_page in enumerate(fitz_doc):
        annots = fitz_page.annots()
        if not annots:
            continue

        page_width = fitz_page.rect.width
        page_height = fitz_page.rect.height
        
        # pdfplumberの対応ページを取得
        if USE_PDFPLUMBER and page_index < len(plumber_doc.pages):
            plumber_page = plumber_doc.pages[page_index]
        else:
            plumber_page = None

        # このページ内のハイライトを処理
        for annot in annots:
            if annot.type[0] == 8:  # 8 = Highlight
                rect = annot.rect
                
                # テキスト抽出方法を選択
                if USE_PDFPLUMBER and plumber_page:
                    text = extract_text_from_rect_pdfplumber(plumber_page, rect, page_height)
                    # pdfplumberで取得できない場合はPyMuPDFにフォールバック
                    if not text:
                        text = extract_text_from_rect_pymupdf(fitz_page, rect)
                else:
                    text = extract_text_from_rect_pymupdf(fitz_page, rect)

                if not text:
                    continue

                # 左右判定
                center_x = (rect.x0 + rect.x1) / 2
                is_left = center_x < (page_width / 2)

                page_num_str = get_footer_number(fitz_page, is_left)
                yomi = get_reading(text)

                data_list.append({
                    "単語": text,
                    "読み": yomi,
                    "ページ数": page_num_str,
                    "ファイル名": filename
                })
    
    fitz_doc.close()
    if USE_PDFPLUMBER:
        plumber_doc.close()

def merge_duplicate_entries(df):
    """
    同じ単語・読み・ファイル名の組み合わせでページ番号をまとめる
    """
    df['ページ数_数値'] = pd.to_numeric(df['ページ数'], errors='coerce')
    
    def merge_pages(pages_series):
        valid_pages = pages_series[pages_series.notna()].astype(int).sort_values().astype(str)
        return ', '.join(valid_pages.unique())
    
    df_merged = df.groupby(['単語', '読み', 'ファイル名'], as_index=False).agg({
        'ページ数': merge_pages
    })
    
    return df_merged

def main():
    target_pdfs = []

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        if os.path.isdir(input_path):
            print(f"フォルダ '{input_path}' 内のPDFを検索します...")
            target_pdfs = glob.glob(os.path.join(input_path, "*.pdf"))
        elif os.path.isfile(input_path):
            if input_path.lower().endswith(".pdf"):
                print(f"ファイル '{input_path}' を処理します...")
                target_pdfs = [input_path]
        else:
            print(f"エラー: '{input_path}' が見つかりません。")
            return
    else:
        print("ファイル指定なし。カレントフォルダのPDFを検索します...")
        target_pdfs = glob.glob("*.pdf")

    if not target_pdfs:
        print("処理対象のPDFファイルが見つかりませんでした。")
        return

    all_data = []
    print(f"対象ファイル数: {len(target_pdfs)}")

    for pdf_file in target_pdfs:
        process_pdf(pdf_file, all_data)

    if not all_data:
        print("ハイライトが見つかりませんでした。")
        return

    df = pd.DataFrame(all_data)
    
    df['ページ数_数値'] = pd.to_numeric(df['ページ数'], errors='coerce')
    df = df.sort_values(by=["読み", "ページ数_数値"])
    
    df_output = df.drop(columns=['ページ数_数値'])
    df_output.to_csv(OUTPUT_FILE, sep='\t', index=False, encoding='utf-8-sig')
    print(f"完了！ '{OUTPUT_FILE}' に保存しました。（全件版）")
    print(f"抽出件数: {len(df_output)} 件")
    
    if MERGE_DUPLICATES:
        df_merged = merge_duplicate_entries(df)
        df_merged = df_merged.sort_values(by=["読み"])
        df_merged.to_csv(OUTPUT_FILE_MERGED, sep='\t', index=False, encoding='utf-8-sig')
        print(f"完了！ '{OUTPUT_FILE_MERGED}' に保存しました。（重複統合版）")
        print(f"統合後件数: {len(df_merged)} 件")

    print("--------------------------------------------------")

if __name__ == "__main__":
    main()