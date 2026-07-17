import fitz  # PyMuPDF
import os
import glob
import argparse

def get_highlighted_text(annot, page):
    """
    ハイライト等の下にある本文テキストを抽出（スペース・改行なしで結合）
    """
    if annot.type[0] not in (8, 9, 10, 11):
        return ""

    text_content = []
    try:
        quads = annot.vertices
        if not quads:
            return ""
        for i in range(0, len(quads), 4):
            quad = fitz.Quad(quads[i], quads[i+1], quads[i+2], quads[i+3])
            text = page.get_text("text", clip=quad.rect).strip()
            if text:
                text_content.append(text)
        
        joined_text = "".join(text_content).replace('\r', '').replace('\n', '')
        return joined_text

    except Exception:
        return ""

def normalize_newlines(text):
    """
    コメント内の改行コードを標準的な '\n' に統一
    """
    if not text:
        return ""
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()

def extract_comments_per_file(input_dir):
    """
    PDFごとに個別のテキストファイルを生成する関数
    （指示者名の出力を削除版）
    """
    input_dir = os.path.abspath(input_dir)
    pdf_files = glob.glob(os.path.join(input_dir, "*.pdf"))
    
    if not pdf_files:
        print(f"エラー: 指定されたフォルダ '{input_dir}' にPDFファイルが見つかりません。")
        return

    print(f"対象フォルダ: {input_dir}")
    print(f"{len(pdf_files)} 個のPDFファイルを処理します...\n")

    success_count = 0

    for pdf_path in pdf_files:
        try:
            folder_path = os.path.dirname(pdf_path)
            file_name_no_ext = os.path.splitext(os.path.basename(pdf_path))[0]
            output_txt_path = os.path.join(folder_path, f"{file_name_no_ext}.txt")

            doc = fitz.open(pdf_path)
            file_comment_count = 0
            
            output_lines = []

            output_lines.append(f"【修正指示書】 {file_name_no_ext}.pdf\n")
            output_lines.append(f"{'='*50}\n\n")

            for page_num, page in enumerate(doc):
                for annot in page.annots():
                    info = annot.info
                    
                    content = normalize_newlines(info.get('content', ''))
                    # author情報は取得しますが、出力には使いません
                    target_text = get_highlighted_text(annot, page)
                    
                    if content or target_text:
                        file_comment_count += 1
                        
                        output_lines.append(f"--------------------------------------------------\n")
                        output_lines.append(f"[ページ]  P.{page_num + 1}\n")
                        # --- [指示者] の出力を削除しました ---
                        
                        if target_text:
                            output_lines.append(f"[対象文]  {target_text}\n")
                        else:
                            output_lines.append(f"[対象文]  (場所指定なし)\n")
                        
                        output_lines.append(f"[指  示]  \n{content}\n")
                        output_lines.append(f"--------------------------------------------------\n\n")

            doc.close()

            if file_comment_count == 0:
                output_lines.append("（このファイルに注釈はありません）\n")

            with open(output_txt_path, mode='w', encoding='utf-8') as f:
                f.writelines(output_lines)

            print(f"作成完了: {os.path.basename(output_txt_path)} ({file_comment_count}件)")
            success_count += 1

        except Exception as e:
            print(f"エラー ({os.path.basename(pdf_path)}): {e}")

    print("-" * 30)
    print(f"処理完了: {success_count}/{len(pdf_files)} ファイル")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDFごとに個別のコメントテキストファイルを作成します。")
    parser.add_argument("input_dir", nargs="?", default=".", help="PDFが入っているフォルダのパス")
    
    args = parser.parse_args()

    extract_comments_per_file(args.input_dir)