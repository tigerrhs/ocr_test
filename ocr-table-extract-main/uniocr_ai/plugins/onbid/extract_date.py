import fitz  # PyMuPDF
import re    # 정규식 모듈
from typing import Dict, Tuple, Optional

TITLE_SEARCH_HEIGHT_RATIO = 0.3  # 상단 30% 영역에서 제목 검사
DATE_SEARCH_HEIGHT_RATIO = 1.8   # 날짜 영역 검색 높이 비율
KEYWORD_MARGIN_LEFT_RATIO = 0.5  # 키워드 왼쪽 여백 비율
KEYWORD_MARGIN_RIGHT_RATIO = 0.3 # 키워드 오른쪽 여백 비율
SEARCH_STEP_RATIO = 0.5          # 검색 스텝 비율

title_pattern = r'.*감[정장]평[가기][료표]\n*'
date_keywords = ['기준시점', '기출사험', '기준사점', '기준시집','기준기람']


def extract_date_info(page_idx: int, page, scale: float) -> Optional[Dict]:
    '''페이지에서 실제 날짜 추출'''
    page_rect = page.rect
    
    # 기준시점 키워드 찾기
    date_bbox = find_date_keyword(page, page_rect)
    if date_bbox is None:
        return {}
    
    # 날짜 정보 추출
    date_info = extract_date_below_keyword(page, date_bbox, page_rect)
    if date_info is None:
        return {}
    
    raw_date, real_rect = date_info
    formatted = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    
    # 결과 반환
    return {
        "text": formatted,
        "page_bbox": [
            {
                "page_num": page_idx,
                "bbox": [
                    round(real_rect.x0 * scale, 2),
                    round(real_rect.y0 * scale, 2),
                    round(real_rect.x1 * scale, 2),
                    round(real_rect.y1 * scale, 2)
                ]
            }
        ],
        "page_size": {
            "width": round(page_rect.width * scale, 2),
            "height": round(page_rect.height * scale, 2)
        }
    }

def find_date_keyword(page, page_rect) -> Optional[Tuple]:
    """페이지에서 '기준시점' 등의 키워드를 찾아 좌표 반환"""
    words_all = page.get_text('words', clip=page_rect)
    max_len = max(len(keyword) for keyword in date_keywords)
    
    for i in range(len(words_all)):
        current = ''
        matched = []

        for j in range(i, len(words_all)):
            chunk = words_all[j][4].replace(' ', '')
            if not chunk:
                continue

            current += chunk
            matched.append(j)

            if len(current) > max_len:
                break
            
            if current in date_keywords:
                xs0 = [words_all[k][0] for k in matched]
                ys0 = [words_all[k][1] for k in matched]
                xs1 = [words_all[k][2] for k in matched]
                ys1 = [words_all[k][3] for k in matched]
                return (min(xs0), min(ys0), max(xs1), max(ys1))
    
    return None

def extract_date_below_keyword(page, date_bbox, page_rect):
    """키워드 아래 영역에서 날짜 정보 추출"""
    x0, y0, x1, y1 = date_bbox
    w = x1 - x0; h = y1 - y0
    margin_left = w * KEYWORD_MARGIN_LEFT_RATIO
    margin_right = w * KEYWORD_MARGIN_RIGHT_RATIO
    step = h * SEARCH_STEP_RATIO

    # 아래로 내려가며 날짜 문자열 찾기
    current_top = y1
    found = None
    candidates = []
    
    while current_top + h * DATE_SEARCH_HEIGHT_RATIO <= page_rect.height and not found:
        dt_rect = fitz.Rect(
            x0 - margin_left,
            current_top,
            x1 + margin_right,
            current_top + h * DATE_SEARCH_HEIGHT_RATIO
        ) 
        lines = page.get_text('text', clip=dt_rect).splitlines()

        if lines:
            for ln in lines:
                candidate = ''.join(re.findall(r'\d', ln))
                if candidate:
                    if len(candidate) == 8:
                        found = (candidate, dt_rect)
                        break
                    elif len(candidate) > 8:
                        found = (candidate[:8], dt_rect)
                        break
                    else:
                        candidates.append((candidate, dt_rect))
        
        if not found:
            words = page.get_text('words', clip=dt_rect)

            text_with_coords = []
            for word in words:
                word_text = word[4].strip()
                digits = ''.join(re.findall(r'\d', word_text))
                if digits:
                    text_with_coords.append({
                        'text': digits,
                        'x0': word[0]
                    })
            if text_with_coords:
                text_with_coords.sort(key=lambda item: item['x0'])
                sorted_candidate = ''.join(item['text'] for item in text_with_coords)

                if len(sorted_candidate) >= 8:
                    found = (sorted_candidate[:8], dt_rect)
                    break
                elif len(sorted_candidate) > 0:
                    candidates.append((sorted_candidate, dt_rect))

        current_top += step
    
    if not found and candidates:
        best_candidate = max(candidates, key=lambda x: len(x[0]))
        found = (best_candidate[0][:8], best_candidate[1])

    if found is None:
        return None
        
    raw_date, dt_rect = found
    real_rect = find_precise_date_rect(page, dt_rect, date_bbox)
    
    return raw_date, real_rect

def find_precise_date_rect(page, dt_rect, date_bbox):
    """날짜의 정확한 위치 찾기"""
    words_in_rect = page.get_text('words', clip=dt_rect)
    x0, y0, x1, y1 = date_bbox
    w = x1 - x0
    margin_left = w * KEYWORD_MARGIN_LEFT_RATIO

    digit_spans = []
    digit_texts = []
    combined = ''
    
    for x0_, y0_, x1_, y1_, wtext_, *_ in words_in_rect:
        txt = wtext_.strip().replace(" ", "")
        cleaned = re.sub(r'\D', '', txt)
        if cleaned.isdigit() and 2 <= len(cleaned) <= 8 and x1 + w*0.2 > (x0_+x1_)//2:
            digit_spans.append((x0_, y0_, x1_, y1_))
            digit_texts.append(cleaned)
            combined = ''.join(digit_texts)
            if len(combined) >= 8:
                combined = combined[:8]  # 잘라서 고정
                break

    if digit_spans:
        # 모든 숫자 영역의 전체 바운딩 박스 계산
        xs0 = [r[0] for r in digit_spans]
        ys0 = [r[1] for r in digit_spans]
        xs1 = [r[2] for r in digit_spans]
        ys1 = [r[3] for r in digit_spans]
        
        # x0 조정: 기준시점의 x0보다 작으면 기준시점 x0를 사용
        min_x0 = min(xs0)
        date_bbox_x0 = date_bbox[0]  # 기준시점의 x0 값
        adjusted_x0 = max(min_x0, date_bbox_x0-margin_left*0.5)
        
        adjusted_y1 = min(ys1)
        
        return fitz.Rect(adjusted_x0, min(ys0), max(max(xs1),date_bbox[2]), adjusted_y1)
    
    return dt_rect