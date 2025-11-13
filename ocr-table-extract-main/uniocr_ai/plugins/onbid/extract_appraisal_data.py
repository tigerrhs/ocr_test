import fitz
import os  # 파일 경로 모듈
import time  # 시간 측정을 위한 모듈

from common_module import message, write_log
from dbquery import error_insert
from onbid.extract_agency import extract_agency_info
from onbid.extract_date import extract_date_info
from onbid.extract_name import extract_appraiser_info


def extract_appraisal_info(pdf_path, cover_page_idx, summary_page_idx, scale, oid):
    '''PDF 파일 처리 및 JSON 저장'''
    # 시간 측정 시작
    start_time = time.time()

    doc = fitz.open(pdf_path)
    error_data = {
        'ERROR_CODE': 'E310',
        'ERROR_MESSAGE': message('E310'),
        'METHOD': ''
    }

    # 감정평가기관 정보 추출
    try:
        cover_page = doc.load_page(cover_page_idx)
        agency = extract_agency_info(cover_page_idx, cover_page, scale)
    except:
        agency = {}
        write_log('감정평가기관 추출 실패', 'ERROR', oid)
        error_data['METHOD'] = '감정평가기관 추출'
        error_insert(error_data, oid)
    
    # 3. 감정평가일 정보 추출
    try:
        summary_page = doc.load_page(summary_page_idx)
        date = extract_date_info(summary_page_idx, summary_page, scale)
    except:
        date = {}
        write_log('감정평가일자 추출 실패', 'ERROR', oid)
        error_data['METHOD'] = '감정평가일자 추출'
        error_insert(error_data, oid)
    
    # 4. 감정평가사 정보 추출
    try:
        appraiser = extract_appraiser_info(summary_page_idx, summary_page, scale)
    except:
        appraiser = {}
        write_log('감정평가사 추출 실패', 'ERROR', oid)
        error_data['METHOD'] = '감정평가사 추출'
        error_insert(error_data, oid)

    write_log(f'[감정평가 정보 추출] (⏱️  {round(time.time() - start_time, 2)}초)', 'INFO', oid)

    return doc, {
        'file_name': os.path.basename(pdf_path),
        'appraisal_agency': agency,
        'appraisal_date': date,
        'appraiser_name': appraiser
    }