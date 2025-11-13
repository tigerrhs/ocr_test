# -*- coding: utf-8 -*-
import json
import os
import time
from typing import Tuple
import traceback

from check_pdf import doc_open_ok
from to_image import get_image_size
from to_pdf import create_pdf, create_image_pdf
from file_manager import ocr_result_PDF2, ocr_result_meta
from ocr import ocr_meta
from onbid.extract_agency import is_cover_page_ocr, is_cover_page_pdf, extract_exact_agency_info
from onbid.extract_titles import extract_page_title_ocr, extract_page_title_pdf, filter_title_fields, text_in_content
from onbid.table_utils import check_detail_page, check_detail_ocr, is_bbox_overlap

os.environ['KMP_DUPLICATE_LIB_OK']='True'
import torch

import easydict
from common_module import Status, write_log
from configs import etc_config, ocr_config
from dbquery import error_insert, ocr_hist_insert
import ocr.ocr_craft as ocr_craft
import threading
from error_message import error_message


# """ OPT 기본 설정값 """
opt = None
# opt_lock = threading.Semaphore()
opt_lock = threading.Lock()

os.environ['CUDA_VISIBLE_DEVICES'] = '0'
title_ratio = float(ocr_config['TITLE_RATIO'])

# OCR 실행 후 결과를 JSON 및 PDF (JSON 내장) 저장
def ocr_run(pageNo, image_path, scale, oid, link_threshold, ocr_rect=None) -> Tuple[dict, str]:
    ocr = ocr_craft

    global opt
    if opt is None:
        error_code = init_opt(oid)
        if error_code:
            insert_error_history(error_code, oid)
            return None, error_code

    errCode = ocr.load_models(opt, oid)
    if errCode:
        return {}, errCode

    ocr_log = f"[OCR] {pageNo}페이지"
    if ocr_rect is None:
        ocr_log += " OCR"
    elif ocr_rect == 'title':
        ocr_log += " 제목 OCR"
    elif ocr_rect == 'detectron':
        ocr_log += " 명세표인지 OCR"
    elif ocr_rect == 'agency':
        ocr_log += " 기관 OCR"
    
    write_log(ocr_log, etc_config['LOG_LEVEL_INFO'], oid)
    
    try:
        image = ocr.load_image(image_path, ocr_rect)
    except Exception as e:
        write_log(str(e), etc_config['LOG_LEVEL_ERROR'], oid)
        return {}, 'E906'

    # detect
    try:
        bboxes = ocr.detect_run(opt, link_threshold, image)
    except Exception as e:
        write_log(str(e), etc_config['LOG_LEVEL_ERROR'], oid)
        return {}, 'E907'

    # classify
    (errCode, page_data) = ocr.classfy_run(opt, pageNo, image_path, bboxes, image, scale, oid)
    if errCode:
        return {}, errCode
    
    page_data['OCR_TYPE'] = ocr_rect if ocr_rect else "FULL"

    # 하단으로 옮기기
    if ocr_rect == "agency":
        offset_y = page_data['PAGE_HEIGHT'] * 0.75
        for field in page_data['FIELDS']:
            field['FIELD_RELM'][1] += offset_y
            field["FIELD_RELM_NOM"][1] = 0.75 + field["FIELD_RELM_NOM"][1] * 0.25

    # JSON 결과값 리턴
    return page_data, errCode

# OPT 설정
def init_opt(oid) -> str:
    write_log("OCR : init_opt", etc_config['LOG_LEVEL_INFO'], oid)
    global opt
    global opt_lock
    with opt_lock:
        if opt is not None:
            return ''
        # opt는 한번만 설정하고 계속 사용해야 함.
        # 모델이 변경되는 경우 서버를 내렸다 다시 올려야 함
        if not opt or opt is None:
            opt = easydict.EasyDict()

            opt.refine_net = None
            opt.canvas_size = 1280

            # cuda / device 재설정
            if torch.cuda.is_available():
                opt.cuda = True
                opt.device = "cuda:0"
            else:
                opt.cuda = False
                opt.device = "cpu"

            opt.workers = 0
            opt.batch_size = 512
            opt.text_threshold = 0.3
            opt.low_text = 0.3
            # opt.link_threshold = 0.8 # property_type에 따라 변경

            opt.mag_ratio = 1.0
            opt.refine = False
            opt.sensitive = True
            opt.rgb = 0
            opt.PAD = 0

            opt.FeatureExtraction = 'ResNet'
            opt.Transformation = 'TPS'
            opt.SequenceModeling = 'BiLSTM'
            opt.Prediction = 'Attn'

            opt.num_fiducial = 20
            opt.batch_max_length = 25
            opt.imgH = 32
            opt.imgW = 150
            opt.input_channel = 1
            opt.output_channel = 512
            opt.hidden_size = 256

            opt.character = './plugins/ocr/character.txt'
            opt.detector = './plugins/ocr/craft_mlt_25k.pth'
            opt.refiner = './plugins/ocr/craft_refiner_CTW1500.pth'
            opt.recognizer = './plugins/ocr/best_accuracy.pth'

            # open file in read mode
            try:
                with open(opt.character, "r", encoding="utf-8-sig") as characterFile:
                    # read the content of file
                    characterData = characterFile.read()
                    #print(f"characterData: {characterData}")
                    opt.character = characterData
                    characterFile.close()

            except Exception as e:
                opt = None
                print(f"Exception: {e}")
                return 'E912'
    return ''


def insert_error_history(errorCode, oid):
    message = error_message.get(errorCode, '존재하지 않는 에러코드입니다.')
    global opt

    # OCR 이력(MD-05) 삽입         GQ-07
    data = {'DOC_NO': None,  # string
            'META_PTH': None,  # string
            'EXEC_TM': None,  # Date(HHmmss)
            'SUCCESS_AT': 0,  # <-- 추가
            'ERROR_MESSAGE': message, # <-- 추가
    }  # string
    isHistoryInsertSuccess = ocr_hist_insert(data, oid)

    if not isHistoryInsertSuccess:
        write_log('OCR History Insert Fail', etc_config['LOG_LEVEL_INFO'],oid)
        error_insert({'ERROR_CODE': 'E919', 'ERROR_MESSAGE': error_message['E919'], 'METHOD': 'OCR'}, oid)


def skip_ocr(i, image_path, scale):
    h, w = get_image_size(image_path, scale)
    return ocr_meta.skip_page(i, image_path, w, h)


def ocr_immovable(doc, orgFileName, originalSavePath, orgTimeStr, pdf_status, image_path_list, detectron_results, rotate, scale, oid):
    metadata = ocr_meta.create(orgFileName, originalSavePath, orgTimeStr)
    cover_page_idx = None
    summary_page_idx = None
    summary_possible = True
    detail_pages = []
    start_time = time.time()
    link_threshold = 0.8

    bug_pdf = False
    if not (doc_open_ok(originalSavePath, doc, image_path_list) or all(status == Status.TEXT for status in pdf_status)):
        # 전체 페이지가 TEXT면 텍스트 PDF를 새로 만들 필요 없으니까 버그도 아니다
        bug_pdf = True
        write_log(f"[OCR] 손상 PDF파일입니다.", etc_config['LOG_LEVEL_WARNING'], oid)

    for i, image_path in enumerate(image_path_list):
        detail_possible = image_path in detectron_results
        if pdf_status[i] == Status.TEXT:    # 텍스트 페이지
            page_data = skip_ocr(i, image_path, scale)
            page = doc.load_page(i)
            ocr_meta.add_page(metadata, page_data)

            if cover_page_idx is None:
                # 나라감정평가법인, 대일감정원
                agency_info = extract_exact_agency_info(cover_page_idx, page, scale)
                if agency_info:
                    cover_page_idx = i
                    continue
                # TODO agency_info return 하는 거 필요

                if is_cover_page_pdf(page, page_data):
                    cover_page_idx = i 
                    agency_data, error_code = ocr_run(i, image_path, scale, oid, link_threshold, 'agency')
                    if error_code:
                        return immovable_ocr_error(error_code, oid)
                    metadata['PAGES'][i]['FIELDS'] = filter_new_fields(page, agency_data['FIELDS'], 'agency')
                    pdf_status[i] = Status.OCR
                    continue

            if summary_possible or detail_possible:
                title_text, title_type = extract_page_title_pdf(page, summary_possible, detail_possible)
                if title_type:
                    if title_type == "감정평가표":
                        summary_page_idx = i
                        summary_possible = False
                    elif title_type == "감정평가명세표":
                        detail_pages.append((i, title_text))

                    if not text_in_content(page):                # 제목 부분이 text인데 내용 부분은 이미지
                        page_data, error_code = ocr_run(i, image_path, scale, oid, link_threshold)
                        if error_code:
                            return immovable_ocr_error(error_code, oid)
                        metadata['PAGES'][i]['FIELDS'] = [field for field in page_data['FIELDS'] if field['FIELD_RELM_NOM'][3] > title_ratio]
                        pdf_status[i] = Status.OCR

                elif detail_possible and len(detectron_results[image_path]) == 1:
                # 제목은 안나왔는데 Detectron돼서 명세표일 수도 있을 때, 명세표는 1페이지에 1개
                    table_rect = [x / scale for x in detectron_results[image_path][0]]
                    if page_data['PAGE_HEIGHT'] * 0.5 < table_rect[3] - table_rect[1]:
                        if check_detail_page(page, table_rect):   # 명세표는 큼
                            detail_pages.append((i, ''))
                        else:
                            title_data, error_code = ocr_run(i, image_path, scale, oid, link_threshold, 'detectron')
                            if error_code:
                                return immovable_ocr_error(error_code, oid)
                            
                            # 명세표 제목 + 컬럼 부분
                            if check_detail_ocr(title_data['FIELDS']):
                                pdf_status[i] = Status.OCR
                                metadata['PAGES'][i]['FIELDS'] = filter_new_fields(page, title_data['FIELDS'], 'detectron')
                                detail_pages.append((i, ''))

        else:   # 이미지 페이지
            if cover_page_idx is None:  # full ocr
                page_data, error_code = ocr_run(i, image_path, scale, oid, link_threshold)
                if error_code:
                    return immovable_ocr_error(error_code, oid)
                pdf_status[i] = Status.OCR
                if is_cover_page_ocr(page_data['FIELDS']):
                    cover_page_idx = i
                elif summary_possible or detail_possible:
                    title_fields = filter_title_fields(page_data)
                    title_text, title_type = extract_page_title_ocr(title_fields, summary_possible, detail_possible)
                    if title_type:
                        if title_type == "감정평가표":
                            summary_page_idx = i
                            summary_possible = False
                        elif title_type == "감정평가명세표" and detail_possible:
                            detail_pages.append((i, title_text))

            elif summary_possible or detail_possible:
                page_data, error_code = ocr_run(i, image_path, scale, oid, link_threshold, 'title')
                if error_code:
                    return immovable_ocr_error(error_code, oid)
                
                title_text, title_type = extract_page_title_ocr(page_data['FIELDS'], summary_possible, detail_possible)
                if title_type:
                    if title_type == "감정평가표":
                        summary_page_idx = i
                        summary_possible = False
                    elif title_type == "감정평가명세표" and detail_possible:
                        detail_pages.append((i, title_text))
                    
                    page_data, error_code = ocr_run(i, image_path, scale, oid, link_threshold)
                    if error_code:
                        return immovable_ocr_error(error_code, oid)
                    pdf_status[i] = Status.OCR

            else:
                page_data = skip_ocr(i, image_path, scale)

            ocr_meta.add_page(metadata, page_data)

    # 표지, 감정평가표 못 찾았을 때
    cover_page_idx = cover_page_idx or 0
    if summary_page_idx is None:
        summary_page_idx = cover_page_idx + 1 if len(pdf_status) > cover_page_idx + 1 else cover_page_idx
        if pdf_status[summary_page_idx] == Status.RAW:
            page_data, error_code = ocr_run(summary_page_idx, image_path_list[summary_page_idx], scale, oid, link_threshold)
            if error_code:
                return immovable_ocr_error(error_code, oid)
            pdf_status[summary_page_idx] = Status.OCR
            metadata['PAGES'][summary_page_idx] = page_data

    page_sizes = [(page["PAGE_WIDTH"], page["PAGE_HEIGHT"]) for page in metadata["PAGES"]]

    # 원본 파일이 텍스트 PDF일 때, OCR 다시 한 거 없을 때
    if all(status == Status.TEXT for status in pdf_status):
        write_log("[TEXT PDF] 원본 파일이 텍스트 PDF 입니다.", etc_config['LOG_LEVEL_INFO'], oid)
        doc.close()
        return originalSavePath, cover_page_idx, summary_page_idx, detail_pages, page_sizes, None

    result_pdf_path = ocr_result_PDF2(orgTimeStr, orgFileName)  # MF-05
    required_pages = {cover_page_idx, summary_page_idx, *[p[0] for p in detail_pages]}   # 필요한 모든 페이지

    if doc:
        pdf_textfields = fields_from_pdf(required_pages, pdf_status, metadata, doc)
        doc.close()
    else:
        pdf_textfields = dict()

    if bug_pdf: # 손상파일
        for i in pdf_textfields:
            metadata['PAGES'][i]['FIELDS'] = pdf_textfields[i]

    # PDF 생성
    try:
        if bug_pdf or doc is None:  # 이미지이거나 손상파일
            create_image_pdf(result_pdf_path, metadata, oid)
        else:
            create_pdf(originalSavePath, result_pdf_path, required_pages, metadata, pdf_status, rotate, pdf_textfields, oid)
        write_log('[TEXT PDF] ' + result_pdf_path, etc_config['LOG_LEVEL_INFO'], oid)
    except:
        traceback.print_exc()
        write_log('[TEXT PDF] 생성 실패', etc_config['LOG_LEVEL_ERROR'], oid) 
        return immovable_ocr_error('E917', oid)
    
    exec_time = time.time() - start_time
    write_log(f'[OCR] {exec_time}초', etc_config['LOG_LEVEL_INFO'], oid)

    # 메타 JSON 생성
    try:
        meta_json_path = create_meta_json(orgTimeStr, orgFileName, result_pdf_path, metadata)
        write_log('[OCR 메타데이터] ' + meta_json_path, etc_config['LOG_LEVEL_INFO'], oid)
    except Exception as e:
        write_log('[OCR 메타데이터] ' + str(e), etc_config['LOG_LEVEL_ERROR'], oid)
        return immovable_ocr_error('E916', oid)
    
    # 이력 삽입
    if ocr_hist(orgFileName, meta_json_path, exec_time, oid):
        write_log('[OCR] 이력 삽입', etc_config['LOG_LEVEL_INFO'], oid)
    else:
        write_log('[OCR] 이력 삽입 실패', etc_config['LOG_LEVEL_ERROR'], oid)
        return immovable_ocr_error('E919', oid)

    return result_pdf_path, cover_page_idx, summary_page_idx, detail_pages, page_sizes, None


def ocr_movable(doc, orgFileName, originalSavePath, orgTimeStr, pdf_status, image_path_list, rotate, scale, oid):
    metadata = ocr_meta.create(orgFileName, originalSavePath, orgTimeStr)
    start_time = time.time()
    link_threshold = 0.2

    # 원본 파일이 텍스트 PDF
    if all(status == Status.TEXT for status in pdf_status):
        return originalSavePath, None

    bug_pdf = False
    if not doc_open_ok(originalSavePath, doc, image_path_list):
        bug_pdf = True
        write_log(f"[OCR] 손상 PDF파일입니다.", etc_config['LOG_LEVEL_WARNING'], oid)

    for i, image_path in enumerate(image_path_list):
        if pdf_status[i] == Status.TEXT:    # 텍스트 페이지
            page_data = skip_ocr(i, image_path, scale)
            ocr_meta.add_page(metadata, page_data)

        else:   # 이미지 페이지
            page_data, error_code = ocr_run(i, image_path, scale, oid, link_threshold)
            if error_code:
                return movable_ocr_error(error_code)
            pdf_status[i] = Status.OCR

            ocr_meta.add_page(metadata, page_data)

    required_pages = set(range(len(image_path_list)))

    if doc:
        pdf_textfields = fields_from_pdf(required_pages, pdf_status, metadata, doc)
        doc.close()
    else:
        pdf_textfields = dict()

    if bug_pdf: # 손상파일
        for i in pdf_textfields:
            metadata['PAGES'][i]['FIELDS'] = pdf_textfields[i]

    result_pdf_path = ocr_result_PDF2(orgTimeStr, orgFileName)  # MF-05

    # PDF 생성
    try:
        if bug_pdf or doc is None:  # 이미지이거나 손상파일
            create_image_pdf(result_pdf_path, metadata, oid)
        else:
            create_pdf(originalSavePath, result_pdf_path, required_pages, metadata, pdf_status, rotate, pdf_textfields, oid)
        write_log('[TEXT PDF] ' + result_pdf_path, etc_config['LOG_LEVEL_INFO'], oid)
    except:
        traceback.print_exc()
        write_log('[TEXT PDF] 생성 실패', etc_config['LOG_LEVEL_ERROR'], oid) 
        return movable_ocr_error('E917', oid)
    
    exec_time = time.time() - start_time
    write_log(f'[OCR] {exec_time}초', etc_config['LOG_LEVEL_INFO'], oid)

    # 메타 JSON 생성
    try:
        meta_json_path = create_meta_json(orgTimeStr, orgFileName, result_pdf_path, metadata)
        write_log('[OCR 메타데이터] ' + meta_json_path, etc_config['LOG_LEVEL_INFO'], oid)
    except Exception as e:
        write_log('[OCR 메타데이터] ' + str(e), etc_config['LOG_LEVEL_ERROR'], oid)
        return movable_ocr_error('E916', oid)
    
    # 이력 삽입
    if ocr_hist(orgFileName, meta_json_path, exec_time, oid):
        write_log('[OCR] 이력 삽입', etc_config['LOG_LEVEL_INFO'], oid)
    else:
        write_log('[OCR] 이력 삽입 실패', etc_config['LOG_LEVEL_ERROR'], oid)
        return movable_ocr_error('E919', oid)

    return result_pdf_path, None


def immovable_ocr_error(error_code, oid):
    insert_error_history(error_code, oid)
    return None, None, None, None, None, error_code


def movable_ocr_error(error_code, oid):
    '''동산 OCR Error'''
    insert_error_history(error_code, oid)
    return None, error_code


def create_meta_json(orgTimeStr, orgFileName, result_pdf_path, metadata):
    meta_json_path = ocr_result_meta(orgTimeStr, orgFileName)
    ocr_meta.set_result_path(metadata, result_pdf_path)
    with open(meta_json_path, 'w', encoding='UTF-8-sig') as outfile:
        json.dump(metadata, outfile, indent=2, ensure_ascii=False)
    return meta_json_path


def ocr_hist(file_name, meta_json_path, exec_time, oid):
    data = {
        'DOC_NO': file_name,  # string
        'META_PTH': meta_json_path,  # string
        'EXEC_TM': exec_time,
        'SUCCESS_AT': 1,
        'ERROR_MESSAGE': ''
    }

    return ocr_hist_insert(data, oid)


def fields_from_pdf(required_pages, pdf_status, metadata, pdf_doc):
    '''텍스트 PDF에서 텍스트 정보 가져와서 필드로 만듬'''
    pdf_fields = dict()
    for i, page in enumerate(pdf_doc):
        if not (i in required_pages and pdf_status[i] == Status.TEXT):
            continue

        width, height = metadata['PAGES'][i]['PAGE_WIDTH'], metadata['PAGES'][i]['PAGE_HEIGHT']
        fields = []
        for j, word in enumerate(page.get_text("words")):
            x0, y0, x1, y1, text, *_ = word
            if not text.strip():
                continue

            fields.append({
                "FIELD_NO": j,
                "FIELD_TEXT": text.strip(),
                "FIELD_RELM": [x0, y0, x1 - x0, y1 - y0],
                "FIELD_RELM_NOM": [x0 / width, y0 / height, x1 / width, y1 / height],
            })
        
        pdf_fields[i] = fields
    return pdf_fields


def filter_new_fields(page, fields, ocr_rect):
    if ocr_rect == 'agency':
        clip = (0, page.rect.height * 0.75, page.rect.width, page.rect.height)
    elif ocr_rect == 'detectron':
        clip = (0, 0, page.rect.width, page.rect.height * 0.25)

    blocks = page.get_text('blocks', clip=clip)
    blocks = [b for b in blocks if b[4].strip() and b[6] == 0]
    new_fields = []
    for field in fields:
        x, y, w, h = [x for x in field["FIELD_RELM"]]
        ocr_box = [x, y, x + w, y + h]

        overlap_found = False
        for block in blocks:
            if is_bbox_overlap(ocr_box, block):
                ix1 = max(block[0], ocr_box[0])
                iy1 = max(block[1], ocr_box[1])
                ix2 = min(block[2], ocr_box[2])
                iy2 = min(block[3], ocr_box[3])
                intersection_area = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                ocr_area = (ocr_box[2] - ocr_box[0]) * (ocr_box[3] - ocr_box[1])
                ratio = intersection_area / ocr_area if ocr_area > 0 else 0

                if ratio > 0.5:
                    if ratio > 0.7:
                        overlap_found = True
                    break

        if not overlap_found:
            new_fields.append(field)

    return new_fields