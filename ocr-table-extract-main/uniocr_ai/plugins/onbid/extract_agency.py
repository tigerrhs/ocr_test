import fitz  # PyMuPDF
import re
from difflib import SequenceMatcher
from configs import path_config
from onbid.table_utils import normalize_text

APPRAISAL_REPORT_PATTERN = re.compile(r'appraisal\s*report', re.IGNORECASE)

# 전역 변수로 기관 목록과 매칭된 텍스트 저장
_agencies = None

def load_agency_list():
    """감정평가기관 목록을 로딩하는 함수"""
    global _agencies
    if _agencies is None:
        agencies = []
        with open(path_config['APPRAISAL_AGENCY_PATH'], 'r', encoding='utf-8') as f:
            for line in f:
                name = line.strip()
                if not name:
                    continue
                agencies.append((name, re.sub(r'[^가-힣a-zA-Z]', '', name)))
        # 길이 기준 내림차순 정렬 (긴 이름이 먼저 비교되도록)
        _agencies = sorted(agencies, key=lambda x: len(x[0]), reverse=True)
    return _agencies

def remove_duplicates(text):
    """중복된 부분 문자열 제거"""
    for length in range(len(text) // 2, 0, -1):
        pattern = text[:length]
        if text.startswith(pattern * (len(text) // length)):
            remainder = text[length * (len(text) // length):]
            if not remainder or pattern.startswith(remainder):
                return pattern
    return text

def find_common_substring_length(text1, text2):
    """difflib을 사용한 공통 부분 문자열 길이 계산"""
    if not text1 or not text2:
        return 0
    return find_common_substring(text1, text2).size


def find_common_substring(text1, text2):
    if not text1 or not text2:
        return None
    matcher = SequenceMatcher(None, text1, text2)
    return matcher.find_longest_match(0, len(text1), 0, len(text2))

def calculate_text_similarity(text1, text2):
    """difflib을 사용한 유사도 계산"""
    if not text1 or not text2:
        return 0.0
    
    # 완전히 같으면 1.0
    if text1 == text2:
        return 1.0
    
    # 너무 짧은 문자열은 간단히 처리
    if len(text1) < 2 or len(text2) < 2:
        return 1.0 if text1 == text2 else 0.0
    
    return SequenceMatcher(None, text1, text2).ratio()

def get_bottom_rect(page):
    """PDF 페이지 하단 20% 영역 반환"""
    return fitz.Rect(
        0,
        0.8 * page.rect.height,
        page.rect.width,
        page.rect.height
    )

def get_upper_rect(page):
    """PDF 페이지 상단 50% 영역 반환"""
    return fitz.Rect(
        0,
        0,
        page.rect.width,
        0.5 * page.rect.height
    )

def extract_bottom_text(page):
    """페이지 하단 20% 영역에서 텍스트 추출"""
    rect = get_bottom_rect(page)
    return page.get_text("text", clip=rect).strip()

def find_agency(text):
    """텍스트에서 감정평가기관명을 찾아 반환 - 매칭된 텍스트도 저장"""
    agencies = load_agency_list()
    
    text = re.sub(r'[^가-힣a-zA-Z]', '', text)
    clean_text = remove_duplicates(text)

    # 1단계: 완전 매칭
    for agency in agencies:
        if clean_text == agency[1]:
            return agency

    # 2단계: 부분 매칭
    curr_len = float("inf")
    max_match_score = 0
    best_agency = ('', '')
    best_matched_text = None

    # 토큰 생성 (기존 로직 유지)
    tokens = [clean_text[i : i + 2] for i in range(len(clean_text) - 1)]
    
    for agency in agencies:
        # difflib으로 계산
        match = find_common_substring(clean_text, agency[1])
        match_length = match.size
        
        if match_length >= 3:
            input_length = len(clean_text)
            match_ratio = match_length / input_length
            token_matches = sum(1 for t in tokens if t in agency[1])
            token_score = token_matches * 0.4
            match_score = match_length + (match_ratio * 10) + token_score

            if match_score > max_match_score:
                max_match_score = match_score
                best_agency = agency
                best_matched_text = clean_text[match.a : match.a + match_length]
            elif match_score == max_match_score:
                prev_len = curr_len
                curr_len = len(agency[1])
                if curr_len < prev_len:
                    best_agency = agency
                    best_matched_text = clean_text[match.a : match.a + match_length]
    
    return best_agency[0], best_matched_text

def get_exact_word_range(word_list, target_text, start_idx):
    """타겟 텍스트에 해당하는 정확한 단어 범위 찾기"""
    if not word_list:
        return None
    
    cumulative_text = ""
    exact_words = []
    target_end = start_idx + len(target_text)
    
    for word in word_list:
        word_text = normalize_text(word[4])
        word_start = len(cumulative_text)
        cumulative_text += word_text
        word_end = len(cumulative_text)

        # 이 단어가 타겟 텍스트와 겹치는지 확인
        if word_start < target_end and word_end > start_idx:
            exact_words.append(word)
        
        # 타겟 범위를 넘어섰으면 중단
        if word_start >= target_end:
            break
    
    return exact_words if exact_words else None

def find_text_in_words(words_in_block, norm_target, scale):
    """words에서 텍스트 찾기 - 정확한 매칭 우선"""
    target_len = len(norm_target)
    
    # 1순위: 정확한 완전 매칭
    for i in range(len(words_in_block)):
        combined_text = ""
        word_boxes = []
        for j in range(i, len(words_in_block)):
            word = words_in_block[j]
            word_text = normalize_text(word[4])
            combined_text += word_text
            word_boxes.append(word)
            
            # 정확히 일치하는 경우
            if combined_text == norm_target:
                min_x0 = min(wb[0] for wb in word_boxes)
                min_y0 = min(wb[1] for wb in word_boxes)
                max_x1 = max(wb[2] for wb in word_boxes)
                max_y1 = max(wb[3] for wb in word_boxes)
                return [
                    round(min_x0 * scale, 2),
                    round(min_y0 * scale, 2),
                    round(max_x1 * scale, 2),
                    round(max_y1 * scale, 2),
                ]
            
            # 타겟이 현재 조합된 텍스트에 포함되는 경우
            if norm_target in combined_text and len(combined_text) <= target_len * 1.5:
                start_idx = combined_text.find(norm_target)
                if start_idx != -1:
                    exact_words = get_exact_word_range(words_in_block[i:j+1], 
                                                        norm_target, start_idx)
                    if exact_words:
                        min_x0 = min(wb[0] for wb in exact_words)
                        min_y0 = min(wb[1] for wb in exact_words)
                        max_x1 = max(wb[2] for wb in exact_words)
                        max_y1 = max(wb[3] for wb in exact_words)
                        return [
                            round(min_x0 * scale, 2),
                            round(min_y0 * scale, 2),
                            round(max_x1 * scale, 2),
                            round(max_y1 * scale, 2),
                        ]
            
            # 너무 길어지면 중단
            if len(combined_text) >= target_len * 2:
                break
    
    # 2순위: 부분 매칭
    for i in range(len(words_in_block)):
        combined_text = ""
        word_boxes = []
        
        for j in range(i, len(words_in_block)):
            word = words_in_block[j]
            word_text = normalize_text(word[4])
            combined_text += word_text
            word_boxes.append(word)
            
            if len(combined_text) >= target_len // 2:
                # difflib 계산
                common_len = find_common_substring_length(combined_text, norm_target)
                
                # 더 엄격한 기준 적용
                if common_len >= max(3, target_len * 0.7):
                    min_x0 = min(wb[0] for wb in word_boxes)
                    min_y0 = min(wb[1] for wb in word_boxes)
                    max_x1 = max(wb[2] for wb in word_boxes)
                    max_y1 = max(wb[3] for wb in word_boxes)
                    return [
                        round(min_x0 * scale, 2),
                        round(min_y0 * scale, 2),
                        round(max_x1 * scale, 2),
                        round(max_y1 * scale, 2),
                    ]
            
            if len(combined_text) >= target_len * 2:
                break
    
    return None

def get_text_position_in_block(page, target_text, block, scale):
    """블록 내 특정 텍스트의 정확한 위치 찾기"""
    block_rect = fitz.Rect(block[0], block[1], block[2], block[3])
    words_in_block = page.get_text("words", clip=block_rect)
    # breakpoint()
    norm_target = normalize_text(target_text)

    # 1단계: words로 정확한 매칭 시도
    words_result = find_text_in_words(words_in_block, norm_target, scale)
    if words_result:
        return words_result

    # 2단계: 실패 시 블록 전체 좌표 반환
    return [
        round(block[0] * scale, 2),
        round(block[1] * scale, 2),
        round(block[2] * scale, 2),
        round(block[3] * scale, 2),
    ]


def find_coords_by_text(search_text, page, matched_seq, use_similarity, scale):
    """텍스트로 좌표 찾기"""
    bottom_rect = get_bottom_rect(page)
    best_match = None
    max_similarity = 0.0
    max_match_len = 0
    simil = False

    blocks = page.get_text("blocks", clip=bottom_rect)
    blocks = [b for b in blocks if b[4].strip() and b[6] == 0]
    for block in blocks:
        block_text = block[4].strip()
        if not block_text:
            continue

        norm_block = normalize_text(block_text)
        
        # (1) 완전 매칭 또는 부분 매칭
        if (
            search_text == norm_block
            or search_text in norm_block
            or norm_block in search_text
        ):
            coords = get_text_position_in_block(page, search_text, block, scale)
            if coords:
                return coords
            return [round(block[i] * scale, 2) for i in range(4)]

        # (2) 유사도 매칭
        if use_similarity:
            sim = calculate_text_similarity(search_text, norm_block)
            if sim > max_similarity and sim > 0.4:
                max_similarity = sim
                coords = get_text_position_in_block(page, search_text, block, scale)
                if coords:
                    best_match = coords
                    simil = True
                else:
                    best_match = [
                        round(block[i] * scale, 2) for i in range(4)
                    ]
                simil = True

            if not simil and matched_seq:
                matcher = SequenceMatcher(None, norm_block, matched_seq)
                match = matcher.find_longest_match(0, len(norm_block), 0, len(matched_seq))
                # print(match.size, norm_block)
                if match.size > max_match_len:
                    coords = get_text_position_in_block(page, matched_seq, block, scale)
                    max_match_len = match.size
                    if coords:
                        best_match = coords

    return best_match


def find_agency_with_coords(agency_name, matched_seq, page, scale):
    """감정평가기관명의 정확한 좌표 찾기 - 지사 없이"""
    agency_name = normalize_text(agency_name)
    return find_coords_by_text(agency_name, page, matched_seq, use_similarity=True, scale=scale)


def find_branch_coords(branch_name, page, scale):
    """지사명 좌표를 좀 더 정확하게 찾기 - 개선된 버전"""
    if not branch_name:
        return None
        
    # 하단 영역에서 블록들을 가져와서 지사명을 찾기
    bottom_rect = get_bottom_rect(page)
    blocks = page.get_text("blocks", clip=bottom_rect)
    blocks = [b for b in blocks if b[4].strip() and b[6] == 0]
    
    # 1단계: 정확한 지사명으로 직접 찾기
    for block in blocks:
        block_text = block[4].strip()
        if not block_text:
            continue

        # 블록 텍스트를 정규화해서 비교
        norm_block = normalize_text(block_text)
        norm_branch = normalize_text(branch_name)

        # 정확히 지사명이 포함되어 있는지 확인
        if norm_branch in norm_block:
            # 블록 내에서 정확한 위치 찾기
            return get_text_position_in_block(page, branch_name, block, scale)
    
    # 2단계: "지사"를 제거하고 지역명만으로 찾기 (예: "경남지사" -> "경남")
    if branch_name.endswith("지사"):
        region_name = branch_name[:-2]  # "경남"
        
        for block in blocks:
            block_text = block[4].strip()
            if not block_text:
                continue
                
            norm_block = normalize_text(block_text)
            norm_region = normalize_text(region_name)
            
            if norm_region in norm_block:
                # 지역명을 찾았다면, 해당 블록에서 지역명 위치를 찾고
                # "지사"가 바로 뒤에 있는지 확인
                return get_text_position_in_block(page, region_name, block, scale)
    
    # 3단계: 문자 단위로 세밀하게 찾기
    if branch_name.endswith("지사"):
        region_name = branch_name[:-2]
        
        # words 단위로 분석해서 지역명과 "지사"를 각각 찾기
        words = page.get_text("words", clip=bottom_rect)
        region_coords = None
        jisa_coords = None
        
        for word in words:
            word_text = normalize_text(word[4])
            
            # 지역명 찾기
            if normalize_text(region_name) in word_text:
                region_coords = [
                    round(word[0] * scale, 2),
                    round(word[1] * scale, 2),
                    round(word[2] * scale, 2),
                    round(word[3] * scale, 2)
                ]
            
            # "지사" 찾기
            if "지사" in word_text:
                jisa_coords = [
                    round(word[0] * scale, 2),
                    round(word[1] * scale, 2),
                    round(word[2] * scale, 2),
                    round(word[3] * scale, 2)
                ]
        
        # 지역명과 "지사"가 모두 발견되었다면 합치기
        if region_coords and jisa_coords:
            return [
                min(region_coords[0], jisa_coords[0]),  # x0
                min(region_coords[1], jisa_coords[1]),  # y0
                max(region_coords[2], jisa_coords[2]),  # x1
                max(region_coords[3], jisa_coords[3])   # y1
            ]
        
        # 지역명만 발견되었다면 지역명 좌표 반환
        if region_coords:
            return region_coords
    
    # 4단계: 유사도 기반 검색
    best_match = None
    max_similarity = 0.0
    
    for block in blocks:
        block_text = block[4].strip()
        if not block_text:
            continue
            
        norm_block = normalize_text(block_text)
        norm_branch = normalize_text(branch_name)
        
        # 유사도 계산
        similarity = calculate_text_similarity(norm_branch, norm_block)
        if similarity > max_similarity and similarity > 0.3:
            max_similarity = similarity
            best_match = get_text_position_in_block(page, branch_name, block, scale)
    
    return best_match

def extract_agency_info(page_idx, page, scale):
    """
    표지 페이지에서 감정평가기관 정보와 지사 정보를 추출하고,
    완전 동일한 bbox는 보정하지 않으며,
    겹칠 때는 기관 중심점까지만 지사 영역을 줄이는 로직 추가
    """
    bottom_text = extract_bottom_text(page)
    full_agency = None
    if bottom_text:
        full_agency, matched_seq = find_agency(bottom_text)

    if not full_agency:
        return {}

    # 기관명·지사명 분리
    if "지사" in full_agency:
        parts = full_agency.rsplit(" ", 1)
        agency_name = parts[0].strip()
        branch_name = parts[1].strip()
    else:
        agency_name = full_agency.strip()
        branch_name = ""

    # 1) 기관 bbox 추출
    agency_coords = find_agency_with_coords(agency_name, matched_seq, page, scale)
    if agency_coords:
        ax0, ay0, ax1, ay1 = agency_coords
    else:
        ax0 = ay0 = ax1 = ay1 = None

    # 2) 지사 bbox 추출
    branch_coords = None
    if branch_name:
        branch_coords = find_branch_coords(branch_name, page, scale)

        if branch_coords:
            bx0, by0, bx1, by1 = branch_coords
        else:
            bx0 = by0 = bx1 = by1 = None
    else:
        bx0 = by0 = bx1 = by1 = None

    # 3) 기관 bbox와 지사 bbox가 둘 다 존재할 때만 보정 검사
    if agency_coords and branch_name and branch_coords:
        same_bbox = (ax0 == bx0 and ay0 == by0 and ax1 == bx1 and ay1 == by1)
        if not same_bbox:
            x_overlap = (bx0 < ax1) and (bx1 > ax0)
            y_overlap = (by0 < ay1) and (by1 > ay0)
            if x_overlap and y_overlap:
                agency_center_x = (ax0 + ax1) / 2
                if bx0 < agency_center_x:
                    bx0 = agency_center_x

    final_agency_bbox = [ax0, ay0, ax1, ay1] if agency_coords else None
    final_branch_bbox = [bx0, by0, bx1, by1] if branch_name and branch_coords else None

    return {
        "name": {
            "text": agency_name,
            "page_bbox": [
                {
                    "page_num": page_idx,
                    "bbox": final_agency_bbox if final_agency_bbox else []
                }
            ]
        },
        "branch": {
            "text": branch_name,
            "page_bbox": [
                {
                    "page_num": page_idx,
                    "bbox": final_branch_bbox if final_branch_bbox else final_agency_bbox
                }
            ]
        },
        "page_size": {
            "width": round(page.rect.width * scale, 2),
            "height": round(page.rect.height * scale, 2)
        }
    }

def is_cover_page_pdf(page, page_data):
    if APPRAISAL_REPORT_PATTERN.search(page.get_text()):
        return True

    texts = page.get_text("blocks", get_upper_rect(page))
    texts = [b for b in texts if b[4].strip() and b[6] == 0]
    for i in texts:
        text = i[4]
        normalized_text = normalize_text(text)
        if '감정평가서' in normalized_text:
            if normalized_text.replace('감정평가서', '') == '':
                if (i[2]- i[0] > page_data['PAGE_WIDTH']*0.2) and (i[3]- i[1] > page_data['PAGE_HEIGHT']*0.03):
                    return True
    
    text = page.get_text(clip=get_bottom_rect(page))
    if any(tel in text.upper().replace(' ', '') for tel in ['전화:', 'TEL:']):
        return True
    return False


def is_cover_page_ocr(page_fields):
    text = ''.join(field['FIELD_TEXT'] for field in page_fields)
    if APPRAISAL_REPORT_PATTERN.search(text):
        return True

    for i in page_fields:
        text = i['FIELD_TEXT']
        normalized_text = normalize_text(text)
        if '감정평가서' in normalized_text:
            if normalized_text.replace('감정평가서', '') == '':
                if (i['FIELD_RELM_NOM'][2]- i['FIELD_RELM_NOM'][0] > 0.2) and (i['FIELD_RELM_NOM'][3]- i['FIELD_RELM_NOM'][1] > 0.03):
                    return True
    return False


def extract_agency_ocr(ocr_fields):
    agencies = load_agency_list()
    text = ''.join(field['FIELD_TEXT'] for field in ocr_fields)
    text = re.sub(r'[^가-힣a-zA-Z]', '', text)
    clean_text = remove_duplicates(text)
    for agency in agencies:
        if clean_text == agency[1]:
            return agency
    return None, None


def extract_exact_agency_info(page_idx, page, scale):
    text = extract_bottom_text(page)
    if not text:
        return None
    
    full_agency = None

    agencies = load_agency_list()
    text = re.sub(r'[^가-힣a-zA-Z]', '', text)
    clean_text = remove_duplicates(text)
    for agency in agencies:
        if agency[1] in clean_text:
            full_agency = agency[0]
            break
    if not full_agency:
        return None

    if "지사" in full_agency:
        parts = full_agency.rsplit(" ", 1)
        agency_name = parts[0].strip()
        branch_name = parts[1].strip()

    else:
        agency_name = full_agency.strip()
        branch_name = ""

    agency_bbox = branch_bbox = []
    
    agency_coords = find_coords_by_text(normalize_text(agency_name), page, matched_seq=None, use_similarity=False, scale=scale)
    if branch_name:
        branch_coords = find_branch_coords(branch_name, page, scale)

    if agency_coords and branch_name and branch_coords:
        ax0, ay0, ax1, ay1 = agency_coords
        bx0, by0, bx1, by1 = branch_coords

        same_bbox = (ax0 == bx0 and ay0 == by0 and ax1 == bx1 and ay1 == by1)
        if not same_bbox:
            x_overlap = (bx0 < ax1) and (bx1 > ax0)
            y_overlap = (by0 < ay1) and (by1 > ay0)
            if x_overlap and y_overlap:
                agency_center_x = (ax0 + ax1) / 2
                if bx0 < agency_center_x:
                    bx0 = agency_center_x

        agency_bbox = [ax0, ay0, ax1, ay1]
        branch_bbox = [bx0, by0, bx1, by1]

    return {
        "name": {
            "text": agency_name,
            "page_bbox": [
                {
                    "page_num": page_idx,
                    "bbox": agency_bbox
                }
            ]
        },
        "branch": {
            "text": branch_name,
            "page_bbox": [
                {
                    "page_num": page_idx,
                    "bbox": branch_bbox if branch_bbox else agency_bbox
                }
            ]
        }
    }