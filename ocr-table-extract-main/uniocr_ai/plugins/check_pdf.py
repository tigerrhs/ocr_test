import fitz
from pdfrw import PdfReader


def open_pdf(pdf_path):
    '''보안 PDF 판단'''
    return fitz.open(pdf_path)


def locked_pdf(doc):
    '''암호화 PDF 판단'''
    return doc.is_encrypted and not doc.authenticate("")


def doc_open_ok(input_file_path, pdf_doc, image_path_list):
    """pdfrw 라이브러리가 모든 페이지를 불러오지 못할 경우
    모든 페이지를 OCR하고 이미지로 PDF를 만들어야 한다"""
    if pdf_doc is None:
        return True
    try:
        reader = PdfReader(input_file_path, decompress=False)
    except:
        return False
    return len(reader.pages) == len(image_path_list)