import fitz  # PyMuPDF
import os
import glob
import argparse
import sys

def get_highlighted_text(annot, page):
    """
    ハイライト等の下にある本文テキストを抽出する関数
    修正点: 改行やスペースが入らないよう、文字を完全に結合します。
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
            # rectで切り抜く際、余計な空白が含まれることがあるのでstripする
            text = page.get_text("text", clip=quad.rect).strip()
            if text:
                text_content.append(text)
        
        # 【修正箇所】
        # join(" ") ではなく join("") に変更（空文字で結合）
        # replaceで改行コードを空文字に置換
        joined_text = "".join(text_content).replace('\r', '').replace('\n', '')
        
        # 念のため、全角・半角スペースも除去したい場合は以下も有効にする（必要に応じて）
        # joined_text = joined_text.replace(' ', '').replace('　', '')
        
        return joined_text

    except Exception:
        return ""

def normalize_newlines(text):
    """
    指示コメント内の改行コードを標準的な '\n' に統一する
    """
    if not text:
        return ""
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()

def batch_extract_to_text(target_folder, output_filepath):
    target_folder = os.path.abspath(target_folder)
    pdf_files = glob.glob(os.path.join(target_folder, "*.pdf"))
    
    if not pdf_files:
        print(f"エラー: 指定されたフォルダ '{target_folder}' にPDFファイルが見つかりません。")
        return

    print(f"対象フォルダ: {target_folder}")
    print(f"{len(pdf_files)} 個のPDFファイルを処理します...")

    try:
        output_dir = os.path.dirname(os.path.abspath(output_filepath))
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_filepath, mode='w', encoding='utf-8') as f:
            
            f.write("【PDF修正指示一覧】\n")
            f.write(f"対象フォルダ: {target_folder}\n")
            f.write("※このファイルは機械的に抽出されたものです。\n\n")

            total_comments = 0

            for pdf_path in pdf_files:
                filename = os.path.basename(pdf_path)
                try:
                    doc = fitz.open(pdf_path)
                    file_buffer = []
                    file_comment_count = 0

                    for page_num, page in enumerate(doc):
                        for annot in page.annots():
                            info = annot.info
                            
                            content_raw = info.get('content', '')
                            content = normalize_newlines(content_raw)
                            
                            author = info.get('title', '')
                            target_text = get_highlighted_text(annot, page)
                            
                            if content or target_text:
                                total_comments += 1
                                file_comment_count += 1
                                
                                file_buffer.append(f"--------------------------------------------------\n")
                                file_buffer.append(f"[ページ]  P.{page_num + 1}\n")
                                file_buffer.append(f"[指示者]  {author}\n")
                                
                                if target_text:
                                    file_buffer.append(f"[対象文]  {target_text}\n")
                                else:
                                    file_buffer.append(f"[対象文]  (場所指定なし/ピンのみ)\n")
                                
                                file_buffer.append(f"[指  示]  \n{content}\n")
                                file_buffer.append(f"--------------------------------------------------\n\n")

                    doc.close()

                    f.write(f"{'='*60}\n")
                    f.write(f"■ ファイル名: {filename}\n")
                    f.write(f"{'='*60}\n\n")

                    if file_comment_count > 0:
                        f.writelines(file_buffer)
                    else:
                        f.write("（このファイルに注釈はありません）\n\n")

                    print(f"完了: {filename} ({file_comment_count}件)")
                    
                except Exception as e:
                    print(f"エラー ({filename}): {e}")
                    f.write(f"※エラー: {filename} の読み込みに失敗しました。\n\n")

        print("-" * 30)
        print(f"全処理が完了しました。")
        print(f"抽出された総コメント数: {total_comments}")
        print(f"保存先: {os.path.abspath(output_filepath)}")

    except Exception as e:
        print(f"ファイル作成中にエラーが発生しました: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDFフォルダ内のコメントを一括抽出し、テキストファイルを作成します。")
    parser.add_argument("input_dir", nargs="?", default=".", help="PDFが入っているフォルダのパス")
    parser.add_argument("-o", "--output", default="correction_list.txt", help="出力するテキストファイルの名前")
    args = parser.parse_args()

    batch_extract_to_text(args.input_dir, args.output)