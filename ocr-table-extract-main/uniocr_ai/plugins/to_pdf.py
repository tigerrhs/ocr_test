import traceback

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab.pdfbase.pdfdoc as pdfdoc

from pdfrw import PdfReader
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl

from common_module import Status, write_log
from configs import pdf_config, etc_config


def pdfdocEnc(x):
    '''create_pdf - c.save() 코덱에 없는 유니코드 예외처리'''
    try:
        return x.encode('extpdfdoc') if isinstance(x,str) else x
    except UnicodeEncodeError:
        return b''
pdfdoc.pdfdocEnc = pdfdocEnc

from common_module import write_log
from configs import pdf_config, etc_config

FONT_NAME = pdf_config['FONT_NAME_LIN']
FONT_FILE = f'./resources/{FONT_NAME}.ttf'

font_scale = float(pdf_config['FONT_SCALE'])
font_fit_in: str = pdf_config['FONT_FIT_IN']

pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))

def get_pdf_pos_y(y:float, height:float) -> float:
    return height - y

def get_max_font_size(w, h, font_name, scale=3.0):
    """
    주어진 영역(w, h)과 폰트 이름, PDF 이미지 스케일을 기준으로 최대 폰트 크기 추정
    """

    font_size_by_height = h * 1.5

    if "Batang" in font_name or "Myungjo" in font_name:
        font_size_by_height *= 1.1

    font_size_scaled = font_size_by_height * scale

    return min(int(font_size_scaled), 150)


def draw_xobj(c:canvas.Canvas, page_obj):
    if page_obj['/CropBox'] is not None:
        (cx, cy, cw, ch) = page_obj['/CropBox']
    else:
        (cx, cy, cw, ch) = page_obj['/MediaBox']

    xobj = pagexobj(page_obj)
    xobj_name = makerl(c, xobj)
    c.saveState()
    c.translate(-float(cx), float(cy)) # CropBox가 시작 좌표가 0이 아닌 경우 처리
    c.doForm(xobj_name)
    c.restoreState()
    return xobj_name


def put_ocr_fields(page, c):
    ph = page['PAGE_HEIGHT']
    fields = page.get('FIELDS')
    if not fields:
        return
    
    c.setFillColorRGB(0, 0, 0, 0)
    ## ED-20250123
    ## 쓰여질 글자의 width가 실제 영역보다 작을경우 블랙마킹이 일부만 되기때문에 강제로 실제 영역에 채워지게 font size up
    old_font_size = -1
    for field in fields:
        t = field['FIELD_TEXT']
        pos = field['FIELD_RELM']
        w = pos[2]
        h = pos[3]
        x = pos[0] + w/2.0
        y = get_pdf_pos_y(pos[1], ph) - h * font_scale

        font_size = h * font_scale
        try:
            if font_fit_in == 'width':  # text가 필수로 함께 있어야만 함
                # 쓰여질 글자의 width가 실제 영역보다 작을경우 블랙마킹이 일부만 되기때문에 강제로 실제 영역에 채워지게 font size up
                font_fit_check_per: float = float(pdf_config['FONT_FIT_CHECK_PER'])
                max_font_size = get_max_font_size(w, h, FONT_NAME, scale=font_scale)
                count = 0
                max_iter = 100

                if c.stringWidth(t, FONT_NAME, font_size) < w * font_fit_check_per:
                    while (c.stringWidth(t, FONT_NAME, font_size)) < w and font_size < max_font_size and count < max_iter:
                        font_size = font_size + 1
                        count += 1
                        if font_size >= max_font_size:
                            break  # 혹은 raise Exception("Max font size exceeded")
        except:
            traceback.print_exc()

        if old_font_size != font_size:
            c.setFont(FONT_NAME, font_size)
            old_font_size = font_size

        c.drawCentredString(x, y, t)


def create_image_pdf(output_file_path, ocr_meta, oid):
    c = canvas.Canvas(output_file_path)
    for page_meta in ocr_meta['PAGES']:
        pw, ph = page_meta['PAGE_WIDTH'], page_meta['PAGE_HEIGHT']
        c.setPageSize((pw, ph))
        c.drawImage(page_meta['PAGE_PATH'], x=0, y=0, width=pw, height=ph, mask=None)
        write_log(f"[draw image] {page_meta['PAGE_NO']}페이지", etc_config['LOG_LEVEL_INFO'], oid)
        put_ocr_fields(page_meta, c)
        c.showPage()
    c.save()


def create_pdf(input_file_path, output_file_path, ocr_pages: set, ocr_meta: dict, pdf_status:list, rotate: dict, pdf_textfields: dict, oid: str):
    """PDF 생성"""
    reader = PdfReader(input_file_path, decompress=False)
    c = canvas.Canvas(output_file_path)

    for i, page_meta in enumerate(ocr_meta['PAGES']):
        pw, ph = page_meta['PAGE_WIDTH'], page_meta['PAGE_HEIGHT']
        c.setPageSize((pw, ph))
        obj = None

        if i in rotate: # 회전 페이지
            c.drawImage(page_meta['PAGE_PATH'], x=0, y=0, width=pw, height=ph, mask=None)
            write_log(f"[draw image] {page_meta['PAGE_NO']}페이지 /Rotate: {rotate[i]}", etc_config['LOG_LEVEL_INFO'], oid)
        else:
            try:
                obj = draw_xobj(c, reader.pages[i])
                write_log(f"[draw xobj] {page_meta['PAGE_NO']}페이지, xobj_name:{obj}", etc_config['LOG_LEVEL_INFO'], oid)

            except:
                c.drawImage(page_meta['PAGE_PATH'], x=0, y=0, width=pw, height=ph, mask=None)
                write_log(f"[draw image] {page_meta['PAGE_NO']}페이지, Error in pagexobj", etc_config['LOG_LEVEL_INFO'], oid)

        if i in ocr_pages:
            if obj is None and pdf_status[i] == Status.TEXT: # 텍스트 페이지였는데 텍스트 정보 없어졌기 때문에 다시 텍스트 가져온다
                ocr_meta['PAGES'][i]['FIELDS'] = pdf_textfields[i]
            put_ocr_fields(page_meta, c)
            write_log(f"[draw OCR] {i}페이지", etc_config['LOG_LEVEL_INFO'], oid)
        c.showPage()
    c.save()