import fitz # PyMuPDF
from PIL import Image

from common_module import page_status, write_log
from configs import etc_config, pdf_config
from file_manager import source_image
from preprocess_image import correct_skew, pix_to_image

PDF_TO_IMAGE_SCALE = float(pdf_config['PDF_TO_IMAGE_SCALE'])

def page_to_image(file_name, page, time_str, uid):
    mat = fitz.Matrix(PDF_TO_IMAGE_SCALE, PDF_TO_IMAGE_SCALE)  # zoom factor 2 in each dimension
    pix = page.get_pixmap(matrix=mat)  # render page to an image
    image_path = source_image(time_str, page.number, 'png', file_name)
    angle = correct_skew(image_path, pix_to_image(pix))
    if angle:
        write_log(f'[page_to_image] path:{image_path}, {angle}˚ rotated', etc_config['LOG_LEVEL_INFO'], uid)
    else:
        pix.save(image_path)  # store image as a PNG
        write_log(f'[page_to_image] path:{image_path}', etc_config['LOG_LEVEL_INFO'], uid)
    return image_path


def to_image(doc, time_str, file_name: str, uid: str):
    '''텍스트PDF 여부 검사, 페이지 이미지 저장을 fitz로 수행'''
    write_log(f'[to_image] 페이지 수: {len(doc)}', etc_config['LOG_LEVEL_INFO'], uid)
    pdf_status = list()
    image_path_list = list()

    rotate = dict()
    for i, page in enumerate(doc):
        pdf_status.append(page_status(page))
        if page.rotation:
            rotate[i] = page.rotation
        page_image_path = page_to_image(file_name, page, time_str, uid)
        image_path_list.append(page_image_path)

    return image_path_list, rotate, pdf_status


def get_image_size(image_file_path, scale):
    # (image_h, image_w, _) = image.shape  # 비상식적으로 height가 먼저 나온다
    # 스캔한 PDF인 경우 image.shape는 width가 먼저 나온다.
    # 경우를 특정하기 애매하기 때문에 PIL로 이미지 크기를 구한다.
    im = Image.open(image_file_path)
    (image_h, image_w) = im.size
    h = image_w / scale
    w = image_h / scale
    im.close()
    return h, w