import re
from common_module import write_log
from configs import etc_config
from onbid.table_utils import copy_field, generate_unique_id, convert_to_pdf_coords, is_bbox_overlap
from onbid.extract_address import address_row_text_groups, build_address_map, process_address, process_location_groups, select_address_group
from onbid.extract_floor_room import process_usage_region_field
from onbid.extract_lot import process_lot_number_field, retain_land_groups
from onbid.table_utils import get_cells_from_row, make_text_groups, merge_cells_info


def create_empty_location_entry():
    """빈 위치 항목 생성"""
    return {
        "address_base": {"id": generate_unique_id(), "text": "", "page_bbox": []}, # 소재지
        "address_dong": {"id": generate_unique_id(), "text": "", "page_bbox": []}, # 지번 동
        "address_floor_room": {"id": generate_unique_id(), "text": "", "page_bbox": []}, # 층/호
        "address_type": {"id": generate_unique_id(), "text": "지번", "page_bbox": []},
        "price": {"id": generate_unique_id(), "text": "", "page_bbox": []},
        "property_usage": {"id": generate_unique_id(), "text": "", "page_bbox": []},
        "area_m2": {"id": generate_unique_id(), "text": "", "page_bbox": []},
    }


def erase_invalid_chars(text):
    return re.sub(r'[^0-9.,]', '', text).strip()


def filter_cells_by_y_overlap(target_cells, reference_cells):
    """
    기준 셀(reference_cells)의 Y 범위와 가장 많이 겹치는 target_cells 반환
    """
    ref_y1 = float("inf")
    ref_y2 = -ref_y1

    for cell in reference_cells:
        bbox = cell.get("text_bbox", [])
        ref_y1 = min(ref_y1, bbox[1])
        ref_y2 = max(ref_y2, bbox[3])

    if ref_y1 == -ref_y2:
        return []

    filtered = []
    max_overlap = -1
    for cell in target_cells:
        y1, y2 = cell["text_bbox"][1], cell["text_bbox"][3]
        overlap = max(0, min(ref_y2, y2) - max(ref_y1, y1))
        if overlap >= (y2 - y1) * 0.5 and overlap >= max_overlap:
            filtered.append(cell)
            max_overlap = overlap

    filtered = [cell for cell in filtered if cell["text_bbox"][1] == filtered[0]["text_bbox"][1]]

    return filtered


def convert_bboxes_to_pdf_coords(result, page_sizes, scale):
    for location_entry in result:
        for field in location_entry:
            entry = location_entry[field]
            page_bbox = entry.get("page_bbox", [])

            big_box = {}
            for pb in page_bbox:
                page_num = pb['page_num']
                bbox = pb['bbox']
                page_height = page_sizes[page_num - 1][1] * scale
                bbox = convert_to_pdf_coords(bbox, page_height, int(scale))

                if page_num in big_box:
                    x1, y1, x2, y2 = big_box[page_num]
                    big_box[page_num] = [min(x1, bbox[0]), min(y1, bbox[1]), max(x2, bbox[2]), max(y2, bbox[3])]
                else:
                    big_box[page_num] = bbox

            entry["page_bbox"] = [{"page_num": page, "bbox": bbox}
                for page, bbox in sorted(big_box.items(), key=lambda kv: kv[0])]
 

def get_valid_row_cells(rows, column_index, row_index, non_empty_only=False):
    """
    주어진 행(row)에서 특정 컬럼의 셀 리스트(cells)를 추출
    - 해당 컬럼이 비어있으면 비어있지 않은 행을 위에서 찾음
    - non_empty_only=True인 경우, text가 비어 있지 않은 셀만 반환
    """
    for i in range(row_index, -1, -1):
        cells = get_cells_from_row(rows[i], column_index, non_empty_only)
        if cells:
            return i, cells
    return -1, None


def get_previous_row_with_cells(data_rows, col_name, group_indices, current_idx):
    """
    이전 행들 중에서 특정 컬럼의 셀 텍스트가 비어있지 않은 첫 번째 행을 반환
    """
    for i in range(current_idx - 1, -1, -1):
        prev_cells = get_cells_from_row(data_rows[i], group_indices[col_name], non_empty_only=True)
        if prev_cells:  # 실제 텍스트가 있는 셀만 유효
            return data_rows[i]
    return None

def property_usage_row_text_groups(group_cells, row_cells):
    text_groups = []

    for cells in group_cells:
        if not cells:
            continue

        group = {'cell': cells, 'used': False}
        text_bboxes = [cell["text_bbox"] for cell in cells if cell.get("text_bbox")]

        if text_bboxes:
            min_x = min(b[0] for b in text_bboxes)
            min_y = min(b[1] for b in text_bboxes)
            max_x = max(b[2] for b in text_bboxes)
            max_y = max(b[3] for b in text_bboxes)
            group['bboxes'] = (min_x, min_y, max_x, max_y)
        else:
            group['bboxes'] = (0, 0, 0, 0)

        group['rows'] = set(cell["row_index"] for cell in cells if cell.get("row_index") is not None)
        format_property_usage_text(group)
        text_groups.append(group)

    row_text_groups = []
    for i, rowcell in enumerate(row_cells):
        available_groups = [g for g in text_groups if not g.get('used', False)]
        matching_groups = []

        for group in available_groups:
            if i in group['rows']:
                matching_groups.append(group)
                continue

            if not rowcell:
                continue

            for cell in rowcell:
                cell_page = cell.get('page', -1)
                group_page = group['cell'][0].get('page', -1) if group['cell'] else -1
                cell_bbox = cell.get("cell_bbox")

                if cell_page == group_page and cell_bbox and is_bbox_overlap(cell_bbox, group['bboxes']):
                    matching_groups.append(group)
                    break

        row_text_groups.append(matching_groups)

    return row_text_groups


def format_property_usage_text(group):
    if not group.get('cell'):
        group['text'] = ""
        return

    texts = []
    seen_texts = set()

    for cell in group['cell']:
        current_text = cell.get("text", "").strip()
        if current_text and current_text not in seen_texts:
            texts.append(current_text)
            seen_texts.add(current_text)

    group['text'] = " ".join(texts) if texts else ""


def standardize_property_usage(location_results):
    standard_formats = {}

    for location in location_results:
        original_text = location["property_usage"]["text"]
        if not original_text:
            continue

        korean_only = re.sub(r'[^가-힣]', '', original_text)

        if korean_only in standard_formats:
            location["property_usage"]["text"] = standard_formats[korean_only]
        else:
            standard_formats[korean_only] = original_text

def process_property_usage_field(location_entry, text_groups):
    if not text_groups:
        return

    unused_groups = [g for g in text_groups if not g.get('used', False)]

    if not unused_groups:
        return

    seen_texts = set()
    unique_texts = []
    all_page_bbox = []

    for group in unused_groups:
        group_text = group.get('text', '').strip()
        if group_text and group_text not in seen_texts:
            unique_texts.append(group_text)
            seen_texts.add(group_text)

            for cell in group.get('cell', []):
                if cell.get("text_bbox"):
                    bbox_info = {"page_num": cell.get("page", 0) + 1, "bbox": cell.get("text_bbox")}
                    all_page_bbox.append(bbox_info)

        group['used'] = True

    if unique_texts:
        final_text = ", ".join(unique_texts)
        location_entry["property_usage"]["text"] = final_text
        location_entry["property_usage"]["page_bbox"] = all_page_bbox


def location_extractor(table, page_sizes, last_location, scale, oid):
    """JSON 파일을 처리하여 위치 별 감정평가액을 추출하는 함수"""
    # 행 가져오기
    group_indices = {value: i for i, value in enumerate(table[0])}
    data_rows = table[1:]

    # 결과 구조 초기화
    result = {}

    # 전체 열 처리: 소재지와 지목 및 용도
    if "소재지" in group_indices:
        location_groups, location_row_cells = make_text_groups(data_rows, group_indices["소재지"])
        location_groups = process_location_groups(location_groups)

    if "지번" in group_indices:
        land_groups, land_row_cells = make_text_groups(data_rows, group_indices["지번"])
        retain_land_groups(land_groups)

    if "소재지" in group_indices:
        if "지번" in group_indices:
            address_map, key_num, last_location = build_address_map(location_groups, land_groups, last_location, oid)
        else:
            last_location = process_address(location_groups, last_location)
            
        location_groups = address_row_text_groups(location_groups, location_row_cells)

    if "지목및용도" in group_indices:
        property_usage_groups, property_usage_row_cells = make_text_groups(data_rows, group_indices["지목및용도"])
        property_usage_row_groups = property_usage_row_text_groups(property_usage_groups, property_usage_row_cells)

    for row_idx, row in enumerate(data_rows):
        location_entry = create_empty_location_entry()

        # === 감정평가액 (복사 없음) ===
        try:
            if "감정평가액" in group_indices:
                price_cells = get_cells_from_row(row, group_indices["감정평가액"], non_empty_only=True)
                text, page_bbox = merge_cells_info(price_cells)

                text = erase_invalid_chars(text)  # 숫자와 쉼표(+온점, 공백)만 가능
                if not text:
                    continue

                location_entry["price"].update({"text": text, "page_bbox": page_bbox})

        except Exception as e:
            write_log(f"[row {row_idx}] 감정평가액 추출 실패: {e}", etc_config['LOG_LEVEL_ERROR'], oid)

        # === 소재지 ===
        try:
            if "소재지" in group_indices:
                location_group = select_address_group(location_groups, row_idx)
                if location_group:
                    if 'point' in location_group:
                        location_group = location_group['point']
                    page_bbox = [
                        {"page_num": cell.get("page", 0) + 1, "bbox": cell.get("text_bbox")}
                        for cell in location_group['cell']
                    ]
                    # 주소 저장
                    if "지번" in group_indices:
                        location_entry["address_base"]["index"] = location_group["index"]
                    location_entry["address_base"]["text"] = location_group["text"]
                    location_entry["address_base"]["page_bbox"] = page_bbox
                    location_entry["address_type"]["page_bbox"] = page_bbox

        except Exception as e:
            write_log(f"[row {row_idx}] 소재지 추출 실패: {e}", etc_config['LOG_LEVEL_ERROR'], oid)

        # === 지목및용도 ===
        try:
            if "지목및용도" in group_indices and property_usage_row_groups:
                matching_groups = property_usage_row_groups[row_idx] if row_idx < len(property_usage_row_groups) else []
                if matching_groups:
                    process_property_usage_field(location_entry, matching_groups)
                else:
                    # fallback 로직
                    prev_entry = next(reversed(result.values()), None)
                    if prev_entry:
                        location_entry["property_usage"]["text"] = prev_entry["property_usage"]["text"]
                        location_entry["property_usage"]["page_bbox"] = prev_entry["property_usage"]["page_bbox"]

        except Exception as e:
            write_log(f"[row {row_idx}] 지목및용도 추출 실패: {e}", etc_config['LOG_LEVEL_ERROR'], oid)
        
        # === 면적 ===
        try:
            if "면적" in group_indices:
                area_cells = get_cells_from_row(row, group_indices["면적"], non_empty_only=True)
                if area_cells and price_cells:
                    filtered_cells = filter_cells_by_y_overlap(area_cells, price_cells)
                    text, page_bbox = merge_cells_info(filtered_cells)
                    text = re.sub(r'\s*,\s*', ',', text)
                    text = re.sub(r'[. ]{1,}', '.', text)
                    text = erase_invalid_chars(text)
                    location_entry["area_m2"].update({"text": text, "page_bbox": page_bbox})

        except Exception as e:
            write_log(f"[row {row_idx}] 면적 추출 실패: {e}", etc_config['LOG_LEVEL_ERROR'], oid)

        result[row_idx] = location_entry

    # === 지번 처리 - 모든 행을 한번에 처리 ===
    try:
        if "지번" in group_indices:
            process_lot_number_field(land_groups, result, address_map, key_num)
    except Exception as e:
        write_log(f"[row {row_idx}] 지번 전체 처리 실패: {e}", etc_config['LOG_LEVEL_ERROR'], oid)

    # === 용도지역및구조 (층/호) - 모든 행을 한번에 처리 ===
    try:
        process_usage_region_field(data_rows, group_indices, result)
    except Exception as e:
        write_log(f"용도지역및구조 전체 처리 실패: {e}", etc_config['LOG_LEVEL_ERROR'], oid)

    # === 후처리: 빈 항목은 이전 항목 값으로 채우기 ===
    try:
        result = list(result.values())
        if len(result) >= 2:
        # 첫번째 행이 없으면 두번째 행에서 가져옴
            if not result[0]["address_base"]["text"]:   # 소재지
                copy_field(result[1], result[0], "address_base")
                copy_field(result[1], result[0], "address_type")
            if not result[0]["address_dong"]["text"] and result[0]["address_base"]["text"] == result[1]["address_base"]["text"]:    # 지번
                copy_field(result[1], result[0], "address_dong")

            if not result[0]["property_usage"]["text"] and result[0]["address_type"]["text"] == result[1]["address_type"]["text"]:   # 지목및용도
                copy_field(result[1], result[0], "property_usage")

        # 두번째 행 부터는 아래에서 가져옴
        for prev, curr in zip(result, result[1:]):
            # 주소체계가 같은 경우에만 복사
            same_address_type = (
                prev["address_type"]["text"] and
                curr["address_type"]["text"] == prev["address_type"]["text"]
            )
            
            if not curr["address_base"]["text"]:
                copy_field(prev, curr, "address_base")
                copy_field(prev, curr, "address_type")

            # 지목및용도는 주소체계만 같으면 복사
            if (same_address_type and not curr["property_usage"]["text"]):
                copy_field(prev, curr, "property_usage")

    except Exception as e:
        write_log(f"[후처리] 빈 항목 채우기 실패: {e}", etc_config['LOG_LEVEL_ERROR'], oid)

    # === 주소 세부항목 병합 및 PDF 좌표 변환 ===
    convert_bboxes_to_pdf_coords(result, page_sizes, scale)

    # === 지목및용도 표준화 ====
    standardize_property_usage(result)
    
    return result, last_location