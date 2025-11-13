import itertools
import re
import uuid
import yaml
from common_module import write_log
from configs import etc_config, path_config

# 공통 키워드 및 조건 정의
mainheader_keyword = {
    '일련번호': ['일련번호', '일련호',  '일번호', '번호', 'No', 'NO'],
    '소재지': ['소재지'],
    '지번': ['지번'],
    '지목및용도': ['지목및용도', '지목', '지목용도', '지목또는용도'],
    '용도지역및구조': ['용도지역및구조', '용도지역구조', '및구조', '용도지역및구', '구조및용도지역', '용도지역또는구조', '용도지역', '구조'],
    '면적': ['면적(㎡)', '면적', '사정'],
    '감정평가액': ['감정평가액', '감정평가금액', '감정평가액원', '평가액', '평가금액', '평가가격원', "금액"],
}

# 층/호 패턴 정규표현식
LAND_PATTERN = r"산?\d+(?:-\d+)?"
DONG_PATTERN = re.compile(r'동(?![가-힣0-9A-Za-z])')
FLOOR_PATTERN = re.compile(r"(제)?(지|지하)?\d+(?:-\d+)?층")  # 제2층, 제2-3층
ROOM_PATTERN = re.compile(r"(제?[가-힣A-Z]*\d+(?:-?[가-힣A-Z\d]+)?호)")   # 제205호, 제에이106호, 에이106호, 비65-1호, 216-제트호, 에이-216호

def generate_unique_id():
    '''유니크한 ID를 생성하는 함수'''
    return str(uuid.uuid4())

def normalize_text(text):
    """띄어쓰기와 특수문자를 제거하고 텍스트를 정규화"""
    if text is None:
        return ""
    
    return re.sub(r"[^가-힣A-Za-z]", "", text)

def convert_to_pdf_coords(bbox, page_height, scale):
    '''PyMuPDF 좌표를 PDF 표준 좌표로 변환하는 함수'''
    # 이미지 스케일로 나누기
    if not bbox or len(bbox) < 4:
        return [0, 0, 0, 0]  # 기본 bbox 반환
    
    scaled_bbox = [coord for coord in bbox]
    
    # PDF 좌표계로 변환 (Y축 뒤집기)
    converted = [
        scaled_bbox[0],                 # x0 (동일)
        page_height - scaled_bbox[3],   # y0 (하단 y 좌표 변환)
        scaled_bbox[2],                 # x1 (동일)
        page_height - scaled_bbox[1],   # y1 (상단 y 좌표 변환)
    ]

    return [round(c / scale, 2) for c in converted]

def merge_values_without_duplicates(v1, v2, separator=", "):
    """두 값을 병합할 때 중복을 제거"""
    if not v1:
        return v2
    if not v2:
        return v1
    
    # 구분자로 값을 분리
    values1 = [v.strip() for v in v1.split(separator) if v.strip()]
    values2 = [v.strip() for v in v2.split(separator) if v.strip()]
    
    # 정규화된 값으로 중복 확인
    normalized_values1 = [normalize_text(v) for v in values1]
    
    # 중복되지 않는 값만 추가
    unique_values2 = []
    for v2_item in values2:
        normalized_v2 = normalize_text(v2_item)
        if normalized_v2 not in normalized_values1:
            unique_values2.append(v2_item)
    
    # 고유한 값 결합
    combined = values1 + unique_values2
    return separator.join(combined)

def find_header_indices(header_rows):
    """헤더에서 특정 키워드가 포함된 컬럼 인덱스를 찾음"""
    group_indices = {group: [] for group in mainheader_keyword}
    
    # 각 컬럼별로 헤더 값 수집 및 키워드 매칭
    for col_idx in range(len(header_rows[0]["values"])):
        header_values = [normalize_text(row["values"][col_idx]["value"]) 
                        for row in header_rows if col_idx < len(row["values"])]
        
        for group, keywords in mainheader_keyword.items():
            # 특수문자가 제거된 키워드와 헤더 값으로 매칭
            normalized_keywords = [normalize_text(kw) for kw in keywords]
            if any(kw in value for value in header_values for kw in normalized_keywords):
                # 메인헤더(면적, 면적)은 뽑혔는데 서브헤더(공부, 사정)이 뽑히지 않은 경우 면적을 구할 수 없어서 서브헤더 매칭 제외함
                group_indices[group].append(col_idx)
    
    return group_indices


def get_cells_from_row(row, column_index, non_empty_only=False):
    """
    주어진 행(row)에서 특정 컬럼(column_index)에 해당하는 셀 리스트(cells)를 추출
    - non_empty_only=True인 경우, text가 비어 있지 않은 셀만 반환
    """
    cells = row[column_index].get("cell", [])
    if non_empty_only:
        # 공백이 아닌 텍스트가 있는 셀만 필터링
        return [cell for cell in cells if cell.get("text", "")]
    return cells


def get_page_vertical_gap(cell):
    '''새 페이지의 vertical gap을 구함'''
    return (cell["text_bbox"][3] - cell["text_bbox"][1]) * 1.1

def make_text_groups(rows, column_index):
    """모든 row에 대하여 text_groups 만들기
    주어진 열에서 모든 행과 인접 행들의 거리를 기반으로 연결된 주소 텍스트를 추출
    - text_bbox 좌표가 인접한 텍스트들을 하나로 묶음
    - 묶인 텍스트의 좌표가 현재 행의 cell_bbox와 겹치는지 확인
    """

    all_cells = []
    row_cells = []    # 각 행의 cells

    for i in range(len(rows)):
        cells = get_cells_from_row(rows[i], column_index, True)
        for cell in cells:
            cell['row_index'] = i
        all_cells.extend(cells)
        row_cells.append(cells)

    if all_cells == []:
        return [], []

    vertical_gap = get_page_vertical_gap(all_cells[0])
    SAME_HORIZONTAL_LINE = 5

    # 모든 cells 그룹화
    text_groups = []
    group = []
    for cell in all_cells:
        if not group:
            group = [cell]
            continue

        last_cell = group[-1]

        same_page = cell['page'] == last_cell['page']
        vertical_adjacent = abs(cell["text_bbox"][1] - last_cell["text_bbox"][3]) <= vertical_gap
        same_line = abs(cell["text_bbox"][1] - last_cell["text_bbox"][1]) <= SAME_HORIZONTAL_LINE

        # 같은 페이지이고, Y좌표가 인접하거나 같은 라인에서 X좌표가 인접하면 그룹화
        if same_page:
            if same_line or vertical_adjacent:
                group.append(cell)
            else:
                text_groups.append(group)
                group = [cell]
        else:
            text_groups.append(group)
            vertical_gap = get_page_vertical_gap(cell)
            group = [cell]
            

    if group:
        text_groups.append(group)

    return text_groups, row_cells


def is_bbox_overlap(bbox1, bbox2):
    """두 bbox가 겹치는지 확인"""
    return not (bbox1[2] < bbox2[0] or bbox1[0] > bbox2[2] or
                bbox1[3] < bbox2[1] or bbox1[1] > bbox2[3])


def merge_cells_info(cells):
    texts = []
    page_bbox = []

    for cell in cells:
        text = cell.get("text", "").strip()
        if text:
            texts.append(text)
            page_bbox.append({
                "page_num": cell.get("page", 0) + 1, 
                "bbox": cell.get("text_bbox")
            })
    
    merged_text = " ".join(texts)

    return merged_text, page_bbox

def extract_land_and_dong(group):
    lands = []
    dongs = []

    cur_row = None
    cur_line = []

    for cell in group:
        if cur_row and cell['row_idx'] != cur_row:
            line_text = ''.join(c['text'] for c in cur_line)    # 줄 바뀔 때 이전 줄 처리
            if line_text == '산':   # 한 줄에 '산'만 있을 때
                cur_row = cell['row_idx']
                cur_line.append(cell)
                continue

            if re.search(DONG_PATTERN, line_text):
                dongs.append(line_text)
            elif not dongs:
                lands.extend(re.findall(LAND_PATTERN, line_text))
            cur_line = []

        cur_row = cell['row_idx']
        cur_line.append(cell)

    # 마지막 줄 처리
    if cur_line:
        line_text = ''.join(c['text'] for c in cur_line)
        if re.search(DONG_PATTERN, line_text):
            dongs.append(line_text)
        elif not dongs:
            lands.extend(re.findall(LAND_PATTERN, line_text))

    return lands, dongs


try:
    with open(path_config['STATE_CITY'], encoding='utf-8') as f:
        state_city = [line.strip() for line in f]
        state_city = "|".join(map(re.escape, state_city))
    with open(path_config['STOPWORDS'], 'r', encoding='utf-8') as f:
        stopwords = yaml.safe_load(f)['불용어사전']
        SAME_KEYWORDS = sorted(stopwords.get('상동관련', []), key=len, reverse=True)
        ROAD_ADDRESS_WORDS = sorted(stopwords.get('도로명주소관련', []), key=len, reverse=True)
        STOPWORDS = sorted(stopwords.get('제시외관련', []), key=len, reverse=True)
except FileNotFoundError as e:
    write_log(e.filename, '파일을 찾을 수 없습니다', etc_config['LOG_LEVEL_ERROR'])


def copy_field(orig, new, field):
    new[field]["text"] = orig[field]["text"]
    new[field]["page_bbox"] = orig[field]["page_bbox"]


def check_detail_page(page, table_rect):
    """페이지 텍스트를 확인해 테이블 안에 컬럼명 키워드가 6개 이상 있고 y 기준으로 너무 멀리 떨어져 있지 않으면 명세표 페이지라고 판단"""
    blocks = page.get_text('blocks', clip=table_rect)
    blocks = [b for b in blocks if b[4].strip() and b[6] == 0]

    if not blocks:
        return False
    column_blocks = {keyword: [] for keyword in mainheader_keyword}
    for b in blocks:
        text = normalize_text(b[4])
        if text:
            for keyword, vocab in mainheader_keyword.items():
                if any(keyword in text for keyword in vocab):
                    column_blocks[keyword].append(b)

    column_blocks = {k: v for k, v in column_blocks.items() if v}

    if len(column_blocks) < 6 or '감정평가액' not in column_blocks:
        return False
    
    max_textsize = max((b[3] - b[1] for b in blocks if '\n' not in b[4].strip()), default=None)
    if max_textsize is None:
        b = blocks[0]
        max_textsize = (b[3] - b[1]) / (b[4].strip().count('\n') + 1)
    threshold = max_textsize * 4

    columns = list(column_blocks.values())
    for combo in itertools.product(*columns):
        max_diff = max(x[3] for x in combo) - min(x[1] for x in combo)
        if max_diff < threshold:
            return True
    return False


def check_detail_ocr(fields):
    """OCR 결과를 확인해 테이블 상단에 컬럼명 키워드가 6개 이상 있으면 명세표 페이지라고 판단"""
    text = normalize_text(''.join(f['FIELD_TEXT'] for f in fields))

    column_blocks = []
    for keyword, vocab in mainheader_keyword.items():
        if any(keyword in text for keyword in vocab):
            column_blocks.append(keyword)

    if len(column_blocks) >= 6 and '감정평가액' in column_blocks:
        return True
    return False