import os

from configs import path_config

def ocr_result_meta(timeStr, orgFileName):
    path = path_config['OCR_RESULT_META_PATH'] + timeStr.strftime('%Y/%m/%d/%H/')
    make_directory(path)
    return path + orgFileName + ".json"

# GF-06, GF-10
# MF-05
def ocr_result_PDF2(timeStr, orgFileName):
    path = path_config['OCR_RESULT_PDF_PATH'] + timeStr.strftime('%Y/%m/%d/%H/')
    make_directory(path)
    return path + orgFileName + ".pdf"

# Source 폴더에 원본 파일을 저장하는 경로를 만들고 파일명도 같이 리턴
def source_original(timeStr, oid, ext):
    time_parts = timeStr.strftime('%Y/%m/%d/%H/')
    path = path_config['SOURCE_ORIGINAL_PATH'] + time_parts
    make_directory(path)

    doc_id = os.path.join(time_parts, oid)
    return path + oid + "." + ext, doc_id

# SOURCE_CREATE = False
def source_original2(timeStr, oid):
    time_parts = timeStr.strftime('%Y/%m/%d/%H/')
    return os.path.join(time_parts, oid)


def make_detectron_directory(timeStr, debug_mode):
    for dir in ['figures', 'jsons']:
        make_directory(path_config['DETECTRON_RESULT_PATH'] + dir + '/' + timeStr.strftime('%Y/%m/%d/%H'))
    if debug_mode:
        make_directory(path_config['DETECTRON_RESULT_PATH'] + 'tables/' + timeStr.strftime('%Y/%m/%d/%H'))

def detectron_table_path(image_path, enumbox):
    image_path = image_path.replace(path_config['SOURCE_IMAGE_PATH'], path_config['DETECTRON_RESULT_PATH'] + 'tables/')
    return image_path.replace('.png', '_' + format(enumbox, '02') + '.png')

def detectron_figure_path(image_path, enumbox):
    image_path = image_path.replace(path_config['SOURCE_IMAGE_PATH'], path_config['DETECTRON_RESULT_PATH'] + 'figures/')
    return image_path.replace('.png', '_' + format(enumbox, '02') + '.png')

def detectron_json_path(timeStr, orgFileName):
    return path_config['DETECTRON_RESULT_PATH'] + 'jsons/' + timeStr.strftime('%Y/%m/%d/%H/') + orgFileName + '.json'

def appraisal_json_path(timeStr, orgFileName):
    path = path_config['APPRAISAL_INFO_PATH'] + timeStr.strftime('%Y/%m/%d/%H')
    make_directory(path)
    return path + '/' + orgFileName + ".json"

def title_table_result(timeStr, orgFileName, title_num):
    return path_config['TABLE_STRUCTURE_PATH'] + 'jsons/' + timeStr.strftime('%Y/%m/%d/%H/') + orgFileName +'_t' + format(title_num, '02')

def page_table_structure_path(timeStr, orgFileName, page_num):
    path = path_config['TABLE_STRUCTURE_PATH'] + 'jsons/' + timeStr.strftime('%Y/%m/%d/%H')
    make_directory(path)
    return path + '/' + orgFileName + '_' + format(page_num, '04') + '.json'

def table_vis_path(timeStr, orgFileName, page_num):
    path = path_config['TABLE_STRUCTURE_PATH'] + 'vis/' + timeStr.strftime('%Y/%m/%d/%H')
    make_directory(path)
    return path + '/' + orgFileName + '_' + format(page_num, '04') + '.jpg'


def page_image_path(table_structure_json):
    path = table_structure_json.rsplit('_', 2)[0] + '.png'
    return path.replace(path_config['TABLE_STRUCTURE_PATH'] + 'jsons/', path_config['SOURCE_IMAGE_PATH'])


def final_result_path(timeStr, orgFileName):
    path = path_config['FINAL_RESULT_PATH'] + timeStr.strftime('%Y/%m/%d/%H')
    make_directory(path)
    return path + '/' + orgFileName + ".json"


# GF-02, GF-03, GF-08, GF-12
# MF-07
def source_image(timeStr, page, ext, fileName):
    path = source_image_fldr(timeStr)
    page_number = format(page, '04')
    return path + fileName + "_" + page_number + "." + ext

# to_image 를 위한 저장 경로 생성 <-- 파일 이름 뒤에 페이지 넘버 (0000.png) 없이
def source_image_fldr(timeStr):
    path = path_config['SOURCE_IMAGE_PATH'] + timeStr.strftime('%Y/%m/%d/%H/')
    make_directory(path)
    return path

# GF-13, GF-15, GF-16
# MF-08
# def source_ocr(timeStr):
#     path = path_config['SOURCE_OCR_PATH'] + timeStr.strftime('%Y/%m/%d/%H/')
#     make_directory(path)
#     count = os.listdir(path)
#     number = format(len(count) + 1, '03')
#     return path_config['SOURCE_OCR_PATH'] + timeStr.strftime('%Y/%m/%d/%H/%M%S') + number + "/"


# def delete_directory(directory_path):
#     try:
#         if os.path.isdir(directory_path):
#             files = os.listdir(directory_path)
#             for file in files:
#                 file_path = os.path.join(directory_path, file)
#                 if os.path.isfile(file_path):
#                     os.remove(file_path)
#                 elif os.path.isdir(file_path):
#                     delete_directory(file_path)
#             os.rmdir(directory_path)
#         elif os.path.isfile(directory_path):
#             os.remove(directory_path)
#     except OSError:
#         print("Error occurred while deleting directory.")
        
def make_directory(directory_path):
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
    except OSError:
        print("Error occurred while making directory.")

# def remove_file(file_path):
#     try:
#         if os.path.exists(file_path):
#             if os.path.isfile(file_path):
#                 os.remove(file_path)
#     except OSError:
#         print("Error occurred while deleting file.")