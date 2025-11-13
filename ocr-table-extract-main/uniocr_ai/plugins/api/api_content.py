# -*- coding: utf-8 -*-
import os

os.environ['KMP_DUPLICATE_LIB_OK']='True'
from flask import make_response
import json
import shutil
import time
import traceback

from onbid.merge_by_serial import merge_by_serial         # 일련번호와 감정평가액 컬럼 기준
from onbid.concat_table import concat_table               # 여러 페이지에 걸쳐 나누어진 표 데이터 병합
from onbid.merge_price_empty import merge_if_price_empty  # 감정평가액이 비어있으면 아래 행과 병합
from onbid.extract_final_result import create_final_json
from ocr.ocr import ocr_immovable, ocr_movable
from check_pdf import open_pdf, locked_pdf
from common_module import Status, message, write_log
from file_manager import appraisal_json_path, source_image, detectron_json_path, source_original, source_original2, title_table_result, final_result_path
from preprocess_image import convert_tiff_to_png, convert_gif_to_png, correct_skew, dec_to_image
from to_image import to_image
from dbquery import error_insert
from detectron2_deploy.detect_crop import detection_request
from configs import etc_config, tatr_config, ocr_config, conv_file_ext, pdf_config
from onbid.extract_appraisal_data import extract_appraisal_info
from onbid.extract_location import location_extractor
from onbid.extract_titles import group_consecutive_pages
from onbid.llama_postpro import post_process_json_file
from onbid.movable_text_pdf_json import movable_text_pdf_json
from tatr.inference import infer as tatr
from onbid.json_postprocessor import normalize_date_fields_in_json
from onbid.json_postprocessor import normalize_price_fields_in_json
from tatr.join_text import join_table_structure_with_pdf_text
from wf.conv_pdf import gen_pdf_doc
from visualization import *

def api_task(*param):
    file_type, orgTimeStr, dec_file, oid, result_save_path, file_basename, original_file_path, property_type = param

    # 서버에도 원본 파일 저장 여부
    if ocr_config['SOURCE_CREATE'] == 'True':
        originalSavePath, doc_id = source_original(orgTimeStr, oid, file_type)
        # 복호화된 jpg / jpeg / png / pdf 원본 파일 저장      MF-06
        with open(originalSavePath, 'wb') as file:
            write_log('복호화된 원본 파일 저장', etc_config['LOG_LEVEL_INFO'], oid)
            file.write(dec_file)
    else:
        doc_id = source_original2(orgTimeStr, oid)
        originalSavePath = original_file_path

    orgFileName = oid   # oid를 파일 이름으로 쓰기

    if file_type in conv_file_ext:
        pdf_path, _ = source_original(orgTimeStr, oid, 'pdf')
        wf_fail = gen_pdf_doc(originalSavePath, pdf_path, oid)
        if wf_fail:
            return response_error_db('E500', 'workflow', oid)
        originalSavePath = pdf_path

    pdf_doc = None
    scale = 1.0
    rotate = dict()

    if file_type in ['jpg', 'jpeg', 'jpe', 'bmp', 'png']:   # 이미지 파일인 경우
        # 이미지 파일 저장 (페이지는 0부터 시작하며 한장의 이미지라 0으로 설정)
        image_save_path = source_image(orgTimeStr, 0, file_type, orgFileName)
        pdf_status = [Status.RAW]

        try:
            angle = correct_skew(image_save_path, dec_to_image(dec_file))
        except:
            response_error_db('E202', 'correct_skew', oid)
        if angle:
            write_log(f'image saved, {angle}˚ rotated',etc_config['LOG_LEVEL_INFO'], oid)
        else:
            try:
                shutil.copy(originalSavePath, image_save_path)
                write_log(f'image saved.', etc_config['LOG_LEVEL_INFO'], oid)
            except Exception as err:
                write_log(str(err), etc_config['LOG_LEVEL_ERROR'], oid)
                return response_error_db('E200', 'save image', oid)
    
        image_path_list = [image_save_path]

    elif file_type == 'gif':
        pdf_status = [Status.RAW]
        try:
            image_save_path = source_image(orgTimeStr, 0, 'png', orgFileName)
            convert_gif_to_png(originalSavePath, image_save_path, oid)
            image_path_list = [image_save_path]
        except:
            write_log(f'[GIF → JPG] 실패 {originalSavePath}', etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E200','save gif image', oid)

    elif file_type == 'tiff' or file_type == 'tif':
        try:
            image_path_list = convert_tiff_to_png(originalSavePath, orgTimeStr, orgFileName, oid)
            pdf_status = [Status.RAW] * len(image_path_list)
        except:
            write_log(f'[TIFF → JPG] 실패 {originalSavePath}', etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E200','save tiff image', oid)

    else:  # PDF 파일인 경우
        # PDF 에서 이미지를 만들고 해당 이미지 파일 저장
        # correct skew 들어있음
        try:
            pdf_doc = open_pdf(originalSavePath)
        except:
            return response_error_db('E918', 'atchmnflPath', oid)
        
        if locked_pdf(pdf_doc):
            return response_error_db('E199', '암호화된 PDF', oid)
        
        try:
            scale = float(pdf_config['PDF_TO_IMAGE_SCALE'])
            image_path_list, rotate, pdf_status = to_image(pdf_doc, orgTimeStr, orgFileName, oid)
        except:
            write_log('PDF 이미지 생성에 실패했습니다.', etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E201', 'save pdf image', oid)

    if property_type == 'immovable':
        # detectron
        detectron_json = detectron_json_path(orgTimeStr, orgFileName)
        figure_savepath = os.path.join(result_save_path, file_basename)
        detectron_results, fig_image_path, error_code = detection_request(image_path_list, detectron_json, orgTimeStr, figure_savepath, oid)
        if error_code:
            write_log(message(error_code), etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db(error_code, 'detectron', oid)
    
        try:
            result_pdf_path, cover_page_idx, summary_page_idx, detail_pages, page_sizes, error_code = ocr_immovable(pdf_doc, orgFileName, originalSavePath, orgTimeStr, pdf_status, image_path_list, detectron_results, rotate, scale, oid)

        except:
            traceback.print_exc()
            write_log("OCR 중 에러 발생", etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E900', 'OCR', oid)

    elif property_type == 'movable':
        try:
            result_pdf_path, error_code = ocr_movable(pdf_doc, orgFileName, originalSavePath, orgTimeStr, pdf_status, image_path_list, rotate, scale, oid)

        except:
            write_log("OCR 중 에러 발생", etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E900', 'OCR', oid)

    if error_code:
        write_log(message(error_code), etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db(error_code, 'OCR', oid)
    
    if file_type != 'pdf':  # 변환 파일은 원본 경로에 텍스트PDF 저장
        pdf_savepath = original_file_path.replace(file_type, 'pdf') # 원본 위치
        shutil.copy(result_pdf_path, pdf_savepath)

    # 동산이면 텍스트 추출하여 JSON으로 변환하고 종료
    if property_type == 'movable':
        try:
            write_log(f'[동산] OCR 데이터를 최종 JSON으로 변환 시작', etc_config['LOG_LEVEL_INFO'], oid)
            movable_final_data = movable_text_pdf_json(result_pdf_path, rotate, oid, doc_id)

            # JSON 저장 경로 설정
            json_savepath = os.path.join(result_save_path, file_basename + '.json')
            
            # UTF-8 형식으로 JSON 파일 저장
            with open(json_savepath, 'w', encoding='utf-8') as f:
                json.dump(movable_final_data, f, ensure_ascii=False, indent=2)
            
            write_log(f'[동산] 간소화된 JSON 변환 완료: {json_savepath}', etc_config['LOG_LEVEL_INFO'], oid)

            # 성공 응답 반환
            response_message = {
                'resultCode': 'E000',
                'resultMessage': message('E000'),
                'savePath': json_savepath
            }
            return make_response(response_message, 200)
        
        except Exception as e:
            write_log(f'[동산] JSON 변환 중 오류: {str(e)}', etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E350', 'text_pdf_to_json', oid)

    detail_titles = group_consecutive_pages(detail_pages)

    pdf_doc, appraisal_info = extract_appraisal_info(result_pdf_path, cover_page_idx, summary_page_idx, scale, oid)
    appraisal_info['table_title'] = detail_titles

    with open(appraisal_json_path(orgTimeStr, orgFileName), 'w', encoding='utf-8') as json_file:
        json.dump(appraisal_info, json_file, ensure_ascii=False, indent=2)


    price_info = []

    # 프로세스별 시작 시간을 저장할 딕셔너리
    process_start_times = {}
    last_location = None    # OCR 오류로 제목이 달라져도 동소를 묶고싶음

    # titles에 해당하는 페이지만 TATR
    for title_num, title_info in enumerate(detail_titles):
        start_page, end_page = title_info['page_range']
        write_log(f"[표 구조 분석] {title_info['text']} page {start_page} ~ {end_page}", etc_config['LOG_LEVEL_INFO'], oid)

        structure_path = []

        with open(detectron_json, 'r') as f:
            page_data = json.load(f)

        for page_num in range(start_page, end_page + 1):
            page_image_path = source_image(orgTimeStr, page_num, file_type, orgFileName).replace('pdf', 'png')

            if page_image_path not in page_data or len(page_data[page_image_path]) == 0:    # 이어지는 페이지에 표가 없으면
                break

            table_xyxy = page_data[page_image_path][0]    # x1, y1, x2, y2
            try:
                # TATR 시작 시간 기록
                process_key = f"TATR_{page_num}"
                process_start_times[process_key] = time.time()

                write_log(f"[TATR 시작] {page_image_path}, table_xyxy: {table_xyxy}", etc_config['LOG_LEVEL_INFO'], oid)
                table_structure_json = tatr(page_image_path, table_xyxy, (orgTimeStr, orgFileName, page_num))

                # 걸린 시간 계산
                elapsed_time = time.time() - process_start_times[process_key]
                write_log(f"[TATR 완료] {table_structure_json} ({elapsed_time:.2f}초)", etc_config['LOG_LEVEL_INFO'], oid)
            except Exception as e:
                write_log(f"[TATR 실패] {str(e)}", etc_config['LOG_LEVEL_ERROR'], oid)
                return response_error_db('E320', 'TATR', oid)
            
            try:
                # OCR+TATR 시작 시간 기록
                process_key = f"OCR_TATR_{page_num}"
                process_start_times[process_key] = time.time()

                write_log( f"[OCR+TATR 시작]", etc_config['LOG_LEVEL_INFO'], oid)
                # page_table_structure = join_table_structure_with_ocr_meta(ocr_data, page_num, table_structure_json, table_xyxy, scale)
                page_table_structure = join_table_structure_with_pdf_text(pdf_doc[page_num], table_structure_json, table_xyxy, scale)

                tocr_path = table_structure_json.replace('.json', '_pts.json')
                with open(tocr_path, "w", encoding="utf-8") as f:
                    json.dump(page_table_structure, f, ensure_ascii=False, indent=2)

                # 걸린 시간 계산
                elapsed_time = time.time() - process_start_times[process_key]
                write_log(f"[OCR+TATR 완료] {tocr_path} ({elapsed_time:.2f}초)", etc_config['LOG_LEVEL_INFO'], oid)

                if tatr_config['debug_mode'] == 'True':
                    visualize_table_boxes(page_image_path, tocr_path, tocr_path.replace('.json', '.png'))
            except Exception as e:
                write_log(f"[OCR+TATR 실패]" + str(e), etc_config['LOG_LEVEL_ERROR'], oid)
                return response_error_db('E320', 'OCR+TATR', oid)

            # OCR 완료 후 행 병합 처리
            merged_path = None
            try:
                # 행 병합 시작 시간 기록
                process_key = f"merge_by_serial_{page_num}"
                process_start_times[process_key] = time.time()

                # 일련번호/감정평가액 기준 병합
                write_log("[일련번호/감정평가액 기준 행 병합]", etc_config['LOG_LEVEL_INFO'], oid)
                merged_result = merge_by_serial(tocr_path, oid)
                if not merged_result:
                    continue
                
                # 행 병합 결과 저장 경로 생성
                merged_path = tocr_path.replace('.json', '_merged.json')
                
                # 결과 저장
                with open(merged_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_result, f, ensure_ascii=False, indent=2)

                # 걸린 시간 계산
                elapsed_time = time.time() - process_start_times[process_key]
                write_log(f"{merged_path} ({elapsed_time:.2f}초)", etc_config['LOG_LEVEL_INFO'], oid)

                if tatr_config['debug_mode'] == 'True':
                    visualize_table_boxes(page_image_path, merged_path, merged_path.replace('.json', '.png'))

            except Exception as e:
                write_log(f"[일련번호/감정평가액 기준 행 병합 실패] " + str(e), etc_config['LOG_LEVEL_ERROR'], oid)
                response_error_db('E320', 'merge rows', oid)
                # 행 병합이 실패해도 원본 OCR 결과로 계속 진행

            if merged_path:
                structure_path.append(merged_path)
            else:
                structure_path.append(tocr_path)

        # 최종적으로 concat 처리
        try:
            # concat 시작 시간 기록
            process_key = f"concat_{title_num}"
            process_start_times[process_key] = time.time()
            
            write_log("[다중 페이지 표 연결 시작]", etc_config['LOG_LEVEL_INFO'], oid)
            header, structure = concat_table(structure_path)
            if not structure:
                continue

            # 걸린 시간 계산
            elapsed_time = time.time() - process_start_times[process_key]
            write_log(f"[다중 페이지 표 연결 완료] 현재 행 수: {len(structure)} ({elapsed_time:.2f}초)", etc_config['LOG_LEVEL_INFO'], oid)

        except Exception as e:
            write_log(f"[다중 페이지 표 연결 실패] " + str(e), etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E320', 'table concat', oid)

        try:
            # 빈 금액 행 병합 시작 시간 기록
            process_key = f"final_merge_{title_num}"
            process_start_times[process_key] = time.time()

            # 감정평가금액 열이 비었을 때 병합
            write_log(f"[빈 금액 행 병합 시작] 현재 행 수: {len(structure)}", etc_config['LOG_LEVEL_INFO'], oid)
            table = merge_if_price_empty(header, structure)

            if table is None:
                write_log(f"❌ [빈 금액 행 병합 실패]", etc_config['LOG_LEVEL_ERROR'], oid)
                continue

            # 걸린 시간 계산
            elapsed_time = time.time() - process_start_times[process_key]
            write_log(f"[빈 금액 행 병합 완료] 병합 후 행 수: {len(table) - 1} ({elapsed_time:.2f}초)", etc_config['LOG_LEVEL_INFO'], oid)

        except Exception as e:
            write_log(f"[빈 금액 행 병합 실패]: {str(e)}", etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E320', 'merge empty', oid)

        # FIXME 빈 금액 병합 시각화
        # for page_num in range(start_page, end_page + 1):
        #     page_image_path = source_image(orgTimeStr, page_num, fileType, orgFileName).replace('pdf', 'png')
        #     visualize_merged_table1(page_image_path, merged_structure, 'debug/' + atchmnfl_name + str(page_num)+'.png', page_num)

        # 빈 금액 병합 표 저장
        if tatr_config['debug_mode'] == 'True':
            title_table_savename = title_table_result(orgTimeStr, orgFileName, title_num)
            with open(title_table_savename + '.json', 'w', encoding='utf-8') as f:
                json.dump(table, f, ensure_ascii=False, indent=2)

            with open(title_table_savename + '.html', 'w', encoding='utf-8') as f:
                f.write(title_table_to_html(table))
                write_log(title_table_savename + '.html', etc_config['LOG_LEVEL_INFO'], oid)

        location_result, last_location = location_extractor(table, page_sizes, last_location, scale, oid)
        price_info.extend(location_result)

    pdf_doc.close()

    try:
        # 최종 JSON 저장 시작 시간 기록
        process_key = "final_json"
        process_start_times[process_key] = time.time()

        final_json = final_result_path(orgTimeStr, orgFileName)
        write_log("[JSON 저장 시작]", etc_config['LOG_LEVEL_INFO'], oid)
        create_final_json(appraisal_info, price_info, page_sizes, final_json, doc_id, original_file_path, fig_image_path, scale, rotate, oid)
        
        json_savepath = os.path.join(result_save_path, file_basename) + '.json'
        shutil.copy(final_json, json_savepath)

        # 걸린 시간 계산
        elapsed_time = time.time() - process_start_times[process_key]
        write_log(f"[JSON 저장 완료] {final_json} ({elapsed_time:.2f}초)", etc_config['LOG_LEVEL_INFO'], oid)

    except Exception as e:
        write_log(f"[JSON 저장 실패] {str(e)}\n{traceback.format_exc()}", etc_config['LOG_LEVEL_ERROR'], oid)
        return response_error_db('E330', 'final_json', oid)

    ## 20250331
    ## json 파일 llama로 후처리
    ## ollama 설치 되어있어야함
    if  etc_config['LLAMA_POSTPRO'] == 'TRUE':
        try:
            write_log(f"[LLAMA POSTPRO] 후처리 작업 중입니다.", etc_config['LOG_LEVEL_INFO'], oid)
            post_process_json_file(final_json, final_json)
            write_log(f"[LLAMA POSTPRO] 후처리 작업 완료.", etc_config['LOG_LEVEL_INFO'], oid)
        except:
            return response_error_db('E340', 'final json sllm', oid)
    else:
        try:
            write_log(f"[POSTPRO] 날짜 정규식 후처리 실행", etc_config['LOG_LEVEL_INFO'], oid)
            normalize_date_fields_in_json(final_json, final_json)
            write_log(f"[POSTPRO] 날짜 정규식 후처리 완료", etc_config['LOG_LEVEL_INFO'], oid)

            write_log(f"[POSTPRO] 가격 정규식 후처리 실행", etc_config['LOG_LEVEL_INFO'], oid)
            normalize_price_fields_in_json(final_json, final_json)
            write_log(f"[POSTPRO] 가격 정규식 후처리 완료", etc_config['LOG_LEVEL_INFO'], oid)
        except Exception as e:
            write_log(f"[POSTPRO] 오류: {str(e)}", etc_config['LOG_LEVEL_ERROR'], oid)
            return response_error_db('E341', 'final json postpro', oid)
        
    shutil.copy(final_json, json_savepath)
    if etc_config['debug_mode'] == 'True':
        final_info_html(final_json)

    # 통신으로 반환할 Response 생성
    response_message = {
        'resultCode': 'E000',
        'resultMessage': message('E000'),
        'savePath': json_savepath
    }
    return make_response(response_message, 200)


def response_error_db(error_code, method, oid):
    result_message = message(error_code)
    response_message = {
        'resultCode': error_code,
        'resultMessage': result_message,
        'savePath': None
    }

    error_data = {
        'ERROR_CODE': error_code,
        'ERROR_MESSAGE': result_message,
        'METHOD': method
    }
    error_insert(error_data, oid)

    return response_message