from copy import deepcopy
from collections import defaultdict
from onbid.table_utils import merge_values_without_duplicates

def merge_if_price_empty(column_name, table):
    """감정평가액에 값이 없는 행이 있을 경우, 그 바로 아래의 행과 병합하여 하나의 행으로 합침"""
    # 헤더 인덱스 추출
    price_col = None
    property_cols = []
    for i, index in enumerate(column_name):
        if index == '감정평가액':
            price_col = i
        elif index == '지목및용도':
            property_cols.append(i)

    if not price_col:
        return None
    col_num = len(column_name)

    # 병합 시작
    new_table = []
    group = []

    for row in table:
        # 병합이 필요한지 여부 판단
        if row[price_col]["merged_text"].strip() == "":
            group.append(row)
        else:
            if group:
                group.append(row)
                new_table.append(merge_rows(group, col_num, property_cols))
                group = []
            else:
                new_table.append(row)

    # 마지막까지 감정평가액이 안 나온 경우
    if group:
        if new_table:  # 위 행이 있으면 위 행과 병합
            last_row = new_table.pop()
            group = [last_row] + group
        new_table.append(merge_rows(group, col_num, property_cols))

    if new_table:
        return [column_name] + new_table

def merge_rows(rows, col_num, property_cols):
    # 병합 수행
    new_row = deepcopy(rows[0])

    for c in range(col_num):
        merged_text = new_row[c]["merged_text"]
        original_cells = new_row[c]["cell"]
        
        # 나머지 행들 처리
        for k in range(1, len(rows)):
            next_cell = rows[k][c]
            v2 = next_cell["merged_text"]

            # 빈 텍스트더라도 cell 정보는 병합
            original_cells.extend(next_cell["cell"])

            if v2:
                if c in property_cols:
                    merged_text = merge_values_without_duplicates(merged_text, v2)
                else:
                    merged_text = (merged_text + " " + v2).strip()  # 공백 정리

        # 페이지별로 병합 bbox 계산 후 각 셀에 적용
        page_to_bboxes = defaultdict(list)
        for cell in original_cells:
            page = cell.get("page")
            if page is not None and cell.get("cell_bbox"):
                page_to_bboxes[page].append(cell["cell_bbox"])

        page_to_merged_bbox = {}
        for page, bboxes in page_to_bboxes.items():
            x0 = min(b[0] for b in bboxes)
            y0 = min(b[1] for b in bboxes)
            x1 = max(b[2] for b in bboxes)
            y1 = max(b[3] for b in bboxes)
            page_to_merged_bbox[page] = [x0, y0, x1, y1]

        for cell in original_cells:
            page = cell.get("page")
            if page in page_to_merged_bbox:
                cell["cell_bbox"] = page_to_merged_bbox[page]

        new_row[c]["merged_text"] = merged_text
        new_row[c]["cell"] = original_cells

    return new_row