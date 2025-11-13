import fitz
import re
from common_module import load_json

def get_x_overlap(a, b):
    a_x0, a_x1 = a[0], a[2]
    b_x0, b_x1 = b[0], b[1]
    return max(0, min(a_x1, b_x1) - max(a_x0, b_x0))

def assign_column_by_overlap(ocr_bbox, column_x):
    max_overlap = 0
    best_col = None
    for col_idx, col_x in column_x.items():
        overlap = get_x_overlap(ocr_bbox, col_x)
        if overlap > max_overlap:
            max_overlap = overlap
            best_col = col_idx
    return best_col

def convert_tatr_bbox(tatr_bbox, detectron_bbox):
    """ TATR 셀 좌표를 디텍트론 절대 좌표로 변환 """
    x1, y1, x2, y2 = tatr_bbox
    dx1, dy1, _, _ = detectron_bbox
    return [x1 + dx1, y1 + dy1, x2 + dx1, y2 + dy1]


def extract_page_number(file_path):
    """ 파일명에서 페이지 번호(예: 0005)를 추출하는 함수 """
    match = re.search(r"/(\d+)_(\d{4})\.json$", file_path)
    page_number = match.group(2)  # "0005" 그룹
    return int(page_number)  # 문자열을 정수(int)로 변환


def extract_table_ocr_data(filtered_ocr_data, table_bbox, scale, inclusion_threshold=0.6):
    """
    OCR JSON에서 특정 페이지와 테이블 영역에 해당하는 필드들만 추출
    """
    table_x1, table_y1, table_x2, table_y2 = table_bbox

    # 결과 필드만 추출
    filtered_fields = []
    for field in filtered_ocr_data["FIELDS"]:
        x, y, w, h = field["FIELD_RELM"]
        new_x = x * scale
        new_y = y * scale
        new_w = w * scale
        new_h = h * scale

        # OCR 영역 좌표
        ocr_x1, ocr_y1 = new_x, new_y
        ocr_x2, ocr_y2 = new_x + new_w, new_y + new_h

        # 테이블과 OCR 영역의 교차 부분 계산
        ix1 = max(table_x1, ocr_x1)
        iy1 = max(table_y1, ocr_y1)
        ix2 = min(table_x2, ocr_x2)
        iy2 = min(table_y2, ocr_y2)

        # 교차 영역이 있는 경우에만 계산
        if ix2 > ix1 and iy2 > iy1:
            # 교차 영역 면적
            intersection_area = (ix2 - ix1) * (iy2 - iy1)
            # OCR 영역 전체 면적
            ocr_area = (ocr_x2 - ocr_x1) * (ocr_y2 - ocr_y1)
            # 포함 비율 계산
            inclusion_ratio = intersection_area / ocr_area
            
            # 테이블에 60% 이상 포함되는 경우만 처리
            if inclusion_ratio >= inclusion_threshold:
                field["FIELD_RELM"] = [ocr_x1, ocr_y1, round(new_w, 2), round(new_h, 2)]    # 페이지 이미지 내 좌표
                filtered_fields.append(field)

    return filtered_fields

def ocr_texts_in_bbox(fields_by_y, cell_bbox):
    x1, y1, x2, y2 = cell_bbox
    matched = []
    for field in fields_by_y:
        fx, fy, fw, fh = field["FIELD_RELM"]
        cx = fx + fw / 2
        cy = fy + fh / 2
        if y1 <= cy <= y2 and x1 <= cx <= x2:
            matched.append(((cy, cx), field["FIELD_TEXT"], [fx, fy, fx + fw, fy + fh]))
    matched.sort()
    return [t[1] for t in matched], [t[2] for t in matched]


def map_ocr_with_cell(tatr_data, ocr_fields, detectron_bbox):
    """OCR텍스트를 테이블 구조에 맵핑
    병합셀은 개별 셀로 나누어 동일한 텍스트를 복제
    특정 조건에서 '공부사정', '공부사', '공'인 경우 텍스트를 분할하여 n번째 열에 '공부', n+1번째 열에 '사정' 삽입.
    """
    new_cells = []
    simple_cells = []  # 병합되지 않은 컬럼헤더 셀 후보
    fields_by_y = sorted(ocr_fields, key=lambda f: f["FIELD_RELM"][1] + f["FIELD_RELM"][3]/2)

    # 1차 처리: 셀 병합 분리 및 텍스트 추출
    for cell in tatr_data:
        cell["cell_bbox"] = convert_tatr_bbox(cell["cell_bbox"], detectron_bbox)

        row_nums = cell["row_nums"]
        col_nums = cell["column_nums"]
        text, text_bbox = ocr_texts_in_bbox(fields_by_y, cell["cell_bbox"])

        for row in row_nums:
            for col in col_nums:
                new_cell = dict(cell)
                new_cell["row_num"] = row
                new_cell["column_num"] = col
                new_cell["text"] = text
                new_cell["text_bbox"] = text_bbox
                new_cells.append(new_cell)

        # 병합되지 않은 컬럼헤더 셀이면 따로 저장
        if cell.get("column header", False) and len(row_nums) == 1 and len(col_nums) == 1:
            simple_cells.append((row, col, new_cell))

    # 2차 처리: 특정 텍스트가 포함된 경우를 n, n+1 열로 분리
    for row, col, cell in simple_cells:
        original_text = "".join(t for t in cell["text"])
        if any(keyword in original_text for keyword in ["공부사정", "공부사", "공부", "공"]):
            cell["text"] = ["공부"]

            # n+1번째 열을 찾아 "사정" 추가
            for next_cell in new_cells:
                if next_cell["row_num"] == row and next_cell["column_num"] == col + 1:
                    next_cell["text"] = ["사정"]
                elif next_cell["row_num"] == row and next_cell["column_num"] == col + 2:
                    next_cell["text"] = [text.replace("사정", "") for text in next_cell["text"]]
                    break
        break
    return new_cells


def pdf_texts_in_bbox(words, cell_bbox):
    x1, y1, x2, y2 = cell_bbox
    matched_words = []
    for word in words:
        if x1 <= word[5] <= x2 and y1 <= word[6] <= y2:
            matched_words.append(word)
    return matched_words


def map_pdf_with_cell(tatr_data, texts_data, detectron_bbox):
    """row_nums 또는 column_nums에 병합된 셀을 개별 셀로 나눠 동일한 텍스트를 복제"""
    new_cells = []

    for cell in tatr_data:
        cell["cell_bbox"] = convert_tatr_bbox(cell["cell_bbox"], detectron_bbox)

        row_nums = cell["row_nums"]
        col_nums = cell["column_nums"]
        matched_words = pdf_texts_in_bbox(texts_data, cell["cell_bbox"])

        for row in row_nums:
            for col in col_nums:
                new_cell = {
                    "cell_bbox": cell["cell_bbox"],
                    "column header": cell["column header"],
                    "row_num": row,
                    "column_num": col,
                    "words": matched_words
                }
                new_cells.append(new_cell)

    return new_cells


def group_rows_by_y(fields, source, tolerance = 10.0, min_y = 0):
    """
    OCR 필드를 기반으로 동일한 y 좌표에 위치한 텍스트들을 하나의 행으로 묶습니다.
    source: OCR / PDF
    tolerance: y좌표의 오차 범위 (같은 행으로 간주할 y좌표 차이)
    """
    grouped_rows = []
    current_row = []

    # 기준이 되는 y 좌표
    previous_center_y = None

    for field in fields:
        if source == 'OCR':
            x, y, w, h = field["FIELD_RELM"]
            center_y = y + h / 2  # 중심 y 좌표 계산
        else:
            center_y = field[6]

        # 컬럼 헤더 영역을 넘어서는 데이터만 처리
        if center_y < min_y:
            continue

        # 이전 y 값과 비교하여 tolerance 내에 있으면 같은 행으로 처리
        if previous_center_y is None or center_y - previous_center_y <= tolerance:
            current_row.append(field)
        else:
            # 다른 행으로 처리
            grouped_rows.append(current_row)
            current_row = [field]

        previous_center_y = center_y

    # 마지막 행 추가
    if current_row:
        grouped_rows.append(current_row)

    return grouped_rows

def additional_column_header(grouped_rows, source):
    '''HEADER_KEYWORDS 중 3개 이상 존재하는 행이 있으면 column header로 추가'''
    HEADER_KEYWORDS = ["구조", "공부", "사정", "단가", "금액", "번호", "용도지역", "소재지", "지번", "비고", "감정평가액"]

    last_valid_index = -1
    last_valid_y = 0
    chance_used = False  # 기회를 한 번만 줄 수 있도록

    for i, row in enumerate(grouped_rows):
        if source == 'OCR':
            row = sorted(row, key=lambda x: x['FIELD_RELM'][0])
            row_text = ''.join(field['FIELD_TEXT'] for field in row).replace(' ', '')
        else:
            row_text = ''.join(word[4] for word in row).replace(' ', '')
        key_count = sum(1 for keyword in HEADER_KEYWORDS if keyword in row_text)

        if key_count >= 3:
            last_valid_index = i
            if source == 'OCR':
                last_valid_y = max(field["FIELD_RELM"][1] + field["FIELD_RELM"][3] for field in row)
            else:
                last_valid_y = max(word[3] for word in row)
            chance_used = False  # 조건 만족했으므로 기회 리셋
        else:
            if not chance_used:
                chance_used = True  # 첫 실패, 기회 소진
                continue
            else:
                break  # 기회 소진 후 실패면 종료

    return last_valid_index, last_valid_y


def scale_texts_data(texts_data, scale):
    """텍스트 PDF의 좌표를 TATR 좌표와 맞추기"""
    new_texts_data = []
    for data in texts_data:
        word = list(w * scale for w in data[:4])
        word.append(data[4])
        word.append((word[0] + word[2]) / 2)    # word[5]
        word.append((word[1] + word[3]) / 2)    # word[6]
        new_texts_data.append(word)
    return new_texts_data


def build_page_table_structure(texts_data, tatr_data, split_cells, source):
    """
    추출된 필드와 TATR 데이터를 기반으로 pts 형식의 JSON을 생성
    병합된 row/column은 개별 셀로 나눠 동일 텍스트를 복제
    """

    column_x = {}
    column_header_row = -1
    column_header_y2 = 0

    # 1. 컬럼 헤더 행 번호 기록
    # 2. 컬럼 헤더의 마지막 y값 저장 (이후 데이터 행 구분 기준)
    for cell in tatr_data:
        if cell.get("column header", False):  # 컬럼 헤더인 경우
            column_header_row = max(column_header_row, max(cell["row_nums"]))
            column_header_y2 = max(column_header_y2, cell["cell_bbox"][3])
        if len(cell["column_nums"]) == 1:
            column_x[cell["column_nums"][0]] = (cell["cell_bbox"][0], cell["cell_bbox"][2])

    total_columns = len(column_x)  # TATR 데이터에서 최대 열 번호 찾기

    # 셀을 행 단위로 그룹화
    header_rows = {r: [-1] * total_columns for r in range(column_header_row + 1)}
    for cell in split_cells:
        row_idx = cell["row_num"]
        if row_idx <= column_header_row:
            header_rows[row_idx][cell["column_num"]] = cell

    table = []

    # 4. 컬럼 헤더 행 먼저 삽입
    for row_index in range(column_header_row + 1):
        if source == "OCR":
            values = ocr_row_values(header_rows[row_index])
        else:
            values = pdf_text_row_values(header_rows[row_index])
        row = {
            "row_index": row_index,
            "column_header": True,
            "values": values
        }
        table.append(row)

    # 5. 컬럼 헤더 이후 행은 OCR 기반으로 행 분리 + 열 배정
    row_index = column_header_row + 1 if column_header_row > -1 else 2  # 컬럼헤더 이후의 행부터 시작
    
    # 컬럼 헤더가 아닌 행을 뒤에 추가, 행 분리 로직 추가
    grouped_rows = group_rows_by_y(texts_data, source, min_y=column_header_y2)

    column_header_row, column_header_y2 = additional_column_header(grouped_rows, source)
    column_header_row += row_index

    for group in grouped_rows:
        row = {
            "row_index": row_index,
            "column_header": row_index <= column_header_row,
            "values": []
        }

        min_y = float('inf')
        max_y = float('-inf')
        texts_by_column = {col: [] for col in range(total_columns)}

        for field in group:
            if source == 'OCR': # OCR 그룹에서 y 좌표 범위 계산 (행의 위아래 좌표)
                x, y, w, h = field["FIELD_RELM"]
                min_y = min(min_y, y)
                max_y = max(max_y, y + h)
                ocr_bbox = [x, y, x + w, y + h]
                text = field["FIELD_TEXT"]

            else:
                x, y1, x2, y2 = field[:4]
                min_y = min(min_y, y1)
                max_y = max(max_y, y2)
                ocr_bbox = field[:4]
                text = field[4]

            col_idx = assign_column_by_overlap(ocr_bbox, column_x)
            if col_idx is not None:
                texts_by_column[col_idx].append((x, text, ocr_bbox))

        for col_idx in range(total_columns):
            texts = texts_by_column.get(col_idx, [])
            texts.sort()
            text_value = [t[1] for t in texts]
            text_bbox = [t[2] for t in texts]
            if col_idx in column_x:
                save_bbox = [
                    column_x[col_idx][0],
                    min_y,
                    column_x[col_idx][1],
                    max_y
                ]

            row["values"].append({
                "value": " ".join(text_value),
                "text": text_value,
                "text_bbox": text_bbox,
                "cell_bbox": save_bbox
            })

        table.append(row)
        row_index += 1 # 행 분리 시마다 +1씩 증가

    return table


def ocr_row_values(row):
    return [{
        "value": " ".join(c["text"]),
        "text": c["text"],
        "text_bbox": c["text_bbox"],
        "cell_bbox": c["cell_bbox"]
    } for c in row]


def pdf_text_row_values(row):
    return [{
        "value": " ".join(word[4] for word in c['words']),
        "text": [word[4] for word in c['words']],
        "text_bbox": [word[:4] for word in c['words']],
        "cell_bbox": c["cell_bbox"]
    } for c in row]


# def join_table_structure_with_ocr_meta(ocr_data, page_number, tatr_json_path, table_bbox, scale):
#     """OCR결과와 TATR 테이블 구조 병합"""
#     # TATR 데이터 로드
#     tatr_data = load_json(tatr_json_path)

#     # OCR 결과에서 특정 페이지 번호만 필터링
#     for page in ocr_data["PAGES"]:
#         if page["PAGE_NO"] == page_number:
#             page_ocr_data = page
#             break

#     if page_ocr_data is None:
#         print(f"경고: OCR 데이터에서 페이지 {page_number}에 해당하는 정보를 찾을 수 없습니다.")
#         return None
    
#     detectron_bbox = table_bbox.copy()

#     # OCR 데이터에서 테이블 영역만 추출
#     table_ocr_data = extract_table_ocr_data(page_ocr_data, table_bbox, scale)

#     # OCR 필드를 y 좌표로 정렬
#     split_cells = map_ocr_with_cell(tatr_data, table_ocr_data, detectron_bbox)

#     table = build_page_table_structure(table_ocr_data, tatr_data, split_cells, "OCR")

#     return {
#         "page_num": page_number,
#         "table": table
#     }


def join_table_structure_with_pdf_text(text_page, tatr_json_path, table_bbox, scale):
    """텍스트PDF의 텍스트 정보와 TATR 테이블 구조 병합"""
    tatr_data = load_json(tatr_json_path)    # TATR 데이터 로드

    texts_data = text_page.get_text("words", clip=[x / scale for x in table_bbox])

    texts_data = scale_texts_data(texts_data, scale)

    texts_data = sorted(texts_data, key=lambda f: f[6])

    split_cells = map_pdf_with_cell(tatr_data, texts_data, table_bbox)

    table = build_page_table_structure(texts_data, tatr_data, split_cells, "PDF")

    return {
        "page_num": text_page.number,
        "table": table
    }