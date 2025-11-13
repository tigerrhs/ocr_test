import fitz  # PyMuPDF
import re    # 정규식 모듈
from configs import path_config
from .extract_agency import normalize_text

# 상수로 분리
TITLE_PATTERN = re.compile(r'.*감[정장]평[가기][료표]\n*')
APPRAISER_PATTERN = re.compile(r'[감강]정평가[가사]')
INVALID_NAME_KEYWORDS = ['법인', '감정', '평가','지사', '사무소','날인','날이','합니다']

# 전역 변수로 성씨 목록 로딩 (한 번만 로딩)
_valid_surnames = None
_valid_two_char_surnames = None

def load_surnames():
    """성씨 목록을 로딩하는 함수"""
    global _valid_surnames, _valid_two_char_surnames
    if _valid_surnames is None:
        with open(path_config['APPRAISAL_FIRST_NAME_PATH'], encoding='utf-8') as f:
            _valid_surnames = set(line.strip() for line in f if line.strip())
        _valid_two_char_surnames = {surname for surname in _valid_surnames if len(surname) == 2}
    return _valid_surnames, _valid_two_char_surnames

# def is_valid_name_candidate(text):
#     """텍스트가 이름일 가능성이 있는지 확인"""
#     return 2 <= len(text) <= 4 and not any(bad in text for bad in INVALID_NAME_KEYWORDS)

def clean_name(name, valid_surnames):
    """이름 후보를 정제하고 중복 문자 제거"""
    # 성씨 처리
    if name[:2] in valid_surnames:
        name = name[:2] + name[2:]
    elif name[0] in valid_surnames:
        name = name[0] + name[1:]
    else:
        name = name[1:]
    
    # 중복 문자 제거
    if len(name) == 4 and name[0] == name[3] and name[:2] not in valid_surnames:
        name = name[:3]
        
    return name

def extract_text_from_region(page, clip):
    """지정된 영역에서 텍스트 추출 및 전처리"""
    raw = page.get_text("text", clip=clip)

    lines = [ln for ln in raw.splitlines() if ln.strip()]
    clean = [ln.replace(' ', '') for ln in lines]
    return lines, clean

def filter_appraiser_lines(lines, clean):
    """감정평가사 키워드 관련 라인 필터링"""
    keyword_pattern = APPRAISER_PATTERN
    skip = set()
    
    # 감정평가사 키워드 패턴 및 제외할 라인 찾기
    for i in range(len(clean)):
        for j in range(i + 1, min(len(clean) + 1, i + 6)):
            concat = ''.join(clean[i:j])
            if keyword_pattern.fullmatch(concat):
                skip.update(range(i, j))
                break

    # 키워드가 포함된 라인 제외
    lines = [ln for idx, ln in enumerate(lines) if idx not in skip]
    lines = [ln for ln in lines if not keyword_pattern.search(ln.replace(' ', ''))]
    
    return lines

def combine_short_lines(lines):
    """짧은 라인이 연속된 경우 결합"""
    if all(len(ln.strip()) <= 2 for ln in lines) and 2 <= len(lines) <= 5:
        extracted = ''.join(ln.strip() for ln in lines)
    else:
        extracted = ''.join(lines)
    return extracted.replace(' ', '').strip()

def find_name_bbox(page, name, clip):
    """이름에 해당하는 BBox 찾기"""
    region_words = page.get_text("words", clip=clip)
    region_words = [w for w in region_words if '감정평가사' not in w[4].replace(' ', '')]

    name_boxes = []
    name_found = False
    
    # 이름과 일치하는 단어 시퀀스 찾기
    for start in range(len(region_words)):
        current = ''
        temp_boxes = []

        for i in range(start, len(region_words)):
            x0, y0, x1, y1, wtext, *rest = region_words[i]
            txt = wtext.replace(' ', '')
            if not txt:
                continue
            current += txt
            temp_boxes.append(fitz.Rect(x0, y0, x1, y1))

            if current == name:
                name_boxes = temp_boxes
                name_found = True
                break
            elif not name.startswith(current):
                break

        if name_found:
            break

    # 박스 합치기
    if name_boxes:
        name_rect = name_boxes[0]
        for box in name_boxes[1:]:
            name_rect |= box
    else:
        # 이름이 포함된 단일 텍스트 박스 찾기
        for x0, y0, x1, y1, wtext, *rest in region_words:
            if name in wtext.replace(' ', ''):
                name_rect = fitz.Rect(x0, y0, x1, y1)
                break
        else:
            name_rect = clip  # 찾지 못한 경우 기본 영역 사용

    return name_rect

def extract_name_from_clip(page, clip, valid_surnames):
    """지정된 영역에서 이름을 추출"""
    # 텍스트 추출 및 전처리
    lines, clean = extract_text_from_region(page, clip)
    
    # 감정평가사 키워드 관련 라인 필터링
    lines = filter_appraiser_lines(lines, clean)

    # INVALID_NAME_KEYWORDS가 포함된 라인 제거
    filtered_lines = []
    for line in lines:
        if APPRAISER_PATTERN.match(line):
            line = line[APPRAISER_PATTERN.match(line).span()[1]+1:]
        if not any(keyword in line.replace(' ', '') for keyword in INVALID_NAME_KEYWORDS):
            filtered_lines.append(line)
    
    # 짧은 라인 결합
    extracted_text = combine_short_lines(filtered_lines)
    
    # 이름 후보 찾기 - 2~4글자 한글 문자만 추출
    candidates = re.findall(r'[가-힣]{2,4}', extracted_text)
    
    if not candidates:
        return '', clip

    name = clean_name(candidates[0], valid_surnames)
    
    # 이름에 해당하는 BBox 찾기
    name_rect = find_name_bbox(page, name, clip)

    return name, name_rect

def create_search_rects(x0, y0, x1, y1, word_w, word_h):
    """검색할 영역들을 생성"""
    # 아래쪽 영역
    down_rects = []
    
    for main_expansion in range(3):
        down_rects.append(fitz.Rect(
            x0 - word_w * 0.2,
            y0 + word_h *0.5* (main_expansion),
            x1 + word_w * 0.2,
            y1 + word_h *0.5* (main_expansion+1)
        ))
    # 오른쪽 영역
    right_rects = []
    start_width = word_w * 0.7
    width_increment = word_w
    sub_width_increment = word_w * 0.3
    
    for main_expansion in range(6):
        main_width = start_width + (width_increment * main_expansion)
        for sub_expansion in range(3):
            sub_width = sub_width_increment * sub_expansion
            current_width = main_width + sub_width
            right_rects.append(fitz.Rect(
                x1,
                y0 - word_h * 0.3,
                x1 + current_width,
                y1 + word_h * 0.3
            ))
    
    return down_rects, right_rects

def find_appraiser_keyword(page, top_half):
    """감정평가사 키워드와 그 위치 찾기"""
    # 감정평가사 키워드 찾기
    words = page.get_text('words', clip=top_half)
    for idx, (x0, y0, x1, y1, wtext, *_) in enumerate(words):
        chunk = wtext.replace(' ', '')
        
        if not chunk or chunk[0] not in {'감', '강'}:
            continue
        
        chunk = normalize_text(chunk)
        # 완전히 일치하는 경우
        if APPRAISER_PATTERN.fullmatch(chunk):
            return (x0, y0, x1, y1, None)
        
        elif APPRAISER_PATTERN.match(chunk):
            sp = APPRAISER_PATTERN.match(chunk).span()
            return (x0, y0, x1, y1, sp)

        # 여러 단어에 걸쳐 있는 경우
        matched = [idx]
        current = chunk
        for j in range(idx + 1, len(words)):
            next_chunk = words[j][4].replace(' ', '')
            if not next_chunk:
                continue
            current += next_chunk
            matched.append(j)
            if APPRAISER_PATTERN.fullmatch(current):
                xs0 = [words[i][0] for i in matched]
                ys0 = [words[i][1] for i in matched]
                xs1 = [words[i][2] for i in matched]
                ys1 = [words[i][3] for i in matched]
                return (min(xs0), min(ys0), max(xs1), max(ys1), None)
            elif APPRAISER_PATTERN.match(chunk):
                sp = APPRAISER_PATTERN.match(chunk).span()
                xs0 = [words[i][0] for i in matched]
                ys0 = [words[i][1] for i in matched]
                xs1 = [words[i][2] for i in matched]
                ys1 = [words[i][3] for i in matched]
                return (min(xs0), min(ys0), max(xs1), max(ys1), sp)
            if len(current) >= 5:  # 최대 길이 제한
                break
    
    return None

def find_name_around_keyword(page, keyword_bbox, valid_surnames):
    """키워드 주변에서 이름 찾기"""
    x0, y0, x1, y1, sp = keyword_bbox
    print(keyword_bbox)

    # if sp:
    #     word_w = x1 - x0
    #     word_h = y1 - y0
    #     # 검색 영역 생성
    #     down_rects, right_rects = create_search_rects_sp(x0, y0, x1, y1, word_w, word_h)
    
    # else:

    word_w = x1 - x0
    word_h = y1 - y0
    # 검색 영역 생성
    down_rects, right_rects = create_search_rects(x0, y0, x1, y1, word_w, word_h)

        # 아래 방향 먼저 탐색
    best_name = ""
    best_name_rect = None

    for rect in down_rects:
        name, name_rect = extract_name_from_clip(page, rect, valid_surnames)
        if name:
            if not best_name:
                best_name =  name
                best_name_rect = name_rect
            elif len(name) == 3 and len(best_name)!=3:
                best_name = name
                best_name_rect = name_rect
            elif len(name) == 2 and (len(best_name)<2 or len(best_name)>3):
                best_name = name
                best_name_rect = name_rect

    
    for rect in right_rects:
        name, name_rect = extract_name_from_clip(page, rect, valid_surnames)
        # 이름을 찾은 경우 저장 (3글자 이름 우선, 없으면 2글자)
        if name:
            if not best_name:
                best_name =  name
                best_name_rect = name_rect
            elif len(name) == 3 and len(best_name)!=3:
                best_name = name
                best_name_rect = name_rect
            elif len(name) == 2 and (len(best_name)<2 or len(best_name)>3):
                best_name = name
                best_name_rect = name_rect

    return best_name, best_name_rect


def extract_appraiser_info(page_idx, page, scale):
    # 성씨 목록 로딩
    valid_surnames, _ = load_surnames()
    page_rect = page.rect
    top_half = fitz.Rect(0, 0, page_rect.width, page_rect.height * 0.5)

    # 감정평가사 키워드 찾기
    keyword_bbox = find_appraiser_keyword(page, top_half)
    if not keyword_bbox:
        return {}
    
    # 키워드 주변에서 이름 찾기
    name, name_rect = find_name_around_keyword(page, keyword_bbox, valid_surnames)

    # 이름을 찾은 경우 결과 반환
    if name and len(name) >= 2:
        return {
            "text": name,
            "page_bbox": [
                {
                    "page_num": page_idx,
                    "bbox": [
                        round(name_rect.x0 * scale, 2),
                        round(name_rect.y0 * scale, 2),
                        round(name_rect.x1 * scale, 2),
                        round(name_rect.y1 * scale, 2)
                    ]
                }
            ],
            "page_size": {
                "width": round(page_rect.width * scale, 2),
                "height": round(page_rect.height * scale, 2)
            }
        }

    return {}