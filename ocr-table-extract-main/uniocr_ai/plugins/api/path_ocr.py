# -*- coding: utf-8 -*-
import os

os.environ['KMP_DUPLICATE_LIB_OK']='True'
import datetime

from api.api_content import api_task, response_error_db
from common_module import read_file, write_log

from configs import etc_config, conv_file_ext, native_file_ext
from visualization import *

def path_ocr(request):
    orgTimeStr = datetime.datetime.now()
    write_log('Path-OCR API 요청', etc_config['LOG_LEVEL_INFO'])

    if request.method != 'POST':
        return
    
    dt = request.json
    oid = dt.get('oid')
    original_file_path = dt.get('pdfPath')
    result_save_path = dt.get('savePath')
    property_type = dt.get('propertyType')

    # 매개변수 검증
    if not (original_file_path and result_save_path):
        write_log(f'필수 매개변수를 확인해주세요.', etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db('E103', 'parameter', oid)
    
    if property_type not in ['movable', 'immovable']:
        write_log(f'propertyType은 movable(동산)/immovable(부동산) 중 하나로 입력해야 합니다.', etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db('E103', 'parameter property', oid)
    
    write_log('작업 파일:' + original_file_path, etc_config['LOG_LEVEL_INFO'], oid)
    filename = os.path.basename(original_file_path)
    file_basename, file_type = os.path.splitext(filename)

    if os.path.exists(original_file_path) == False:
        write_log(f'요청 파일이 존재하지 않습니다.', etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db('E101', 'original_file_path', oid)
    
    if os.path.exists(result_save_path) == False:
        write_log(f'저장 경로가 올바르지 않습니다.', etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db('E104', 'result_save_path', oid)

    file_type = file_type[1:].lower() if len(file_type) else ''
    if file_type not in native_file_ext + conv_file_ext:
        write_log('유효하지 않은 파일 타입: ' + file_type, etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db('E102', 'file type: ' + file_type, oid)

    dec_file = read_file(original_file_path)
    if not dec_file:
        write_log('파일이 올바르지 않습니다.', etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db('E918', 'atchmnflPath', oid)


    result = api_task(file_type, orgTimeStr, dec_file, oid, result_save_path, file_basename, original_file_path, property_type)

    return result