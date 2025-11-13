import copy
from common_module import load_json, write_log
from configs import etc_config
from onbid.table_utils import find_header_indices, normalize_text, FLOOR_PATTERN, ROOM_PATTERN

def keyword_in_index(row, indices, keywords, normalize=True):
    for index in indices:
        text = row["values"][index]["value"]
        if normalize:
            text = normalize_text(text)
        for keyword in keywords:
            if keyword in text:
                return True
    return False


def contains_invalid_keyword(row, price_indices, address_indices, area_indices):
    # 감정평가액 필터
    if keyword_in_index(row, price_indices, ["₩", "￦", "\\", "배분", "토지", "건물", "내역", "여백"], False):
        return True

    # 소재지 컬럼 값이 '소계'일 경우
    if keyword_in_index(row, address_indices, ["소계"]):
        return True
            
    # 면적 컬럼에 '토지', '건물'이 포함된 경우 제거
    if keyword_in_index(row, area_indices, ["토지", "건물"]):
        return True

    return False


def is_total(row, address_indices):
    text = ''.join(normalize_text(row["values"][index]["value"]) for index in address_indices)
    return len(text) == 2 and text[0] == '합'
        

def is_floor_info(row, structure_indices):
    for struct_idx in structure_indices:
        value = row["values"][struct_idx]["value"].strip()
        floor_match = FLOOR_PATTERN.search(value)
        if floor_match:
            after_floor = value[floor_match.end():]  # 층 끝난 다음부터
            if ROOM_PATTERN.search(after_floor):
                return True
    return False


def group_and_merge_rows(data, oid):
    """테이블 행을 병합하고, '사정' 면적 값은 감정평가액이 있는 행에 한해 1개만 유지."""

    # 헤더와 데이터 행 분리
    header_rows = [row for row in data["table"] if row.get("column_header")]
    data_rows = [row for row in data["table"] if not row.get("column_header")]

    rows_len = len(data_rows)

    # 첫 번째 데이터 행의 y좌표 조정
    if header_rows and data_rows:
        max_header_y = header_rows[-1]["values"][0]["cell_bbox"][3]
        for cell in data_rows[0]["values"]:
            cell["cell_bbox"][1] = max_header_y

    # 헤더 컬럼 인덱스 찾기
    indices = find_header_indices(header_rows)
    serial_indices = indices.get('일련번호', [])
    price_indices = indices.get('감정평가액', [])
    address_indices = indices.get("소재지", [])
    property_indices = indices.get('지목및용도', [])
    area_indices = indices.get('면적', [])
    structure_indices = indices.get('용도지역및구조', [])

    # 키워드를 찾지 못한 경우 원본 반환
    if not price_indices:
        write_log(f"감정평가액 컬럼을 찾을 수 없습니다.", etc_config['LOG_LEVEL_INFO'], oid)
        return None
    
    def has_value(row, indices):
        return any(row["values"][idx]["value"].strip() for idx in indices)

    # group_by_upper 여부 판단 (첫 데이터 행에 일련번호 있는지)
    group_by_upper = has_value(data_rows[0], serial_indices)

    # 행 그룹화
    groups = []
    current = []

    if group_by_upper:
        # 위에서 아래로 그룹화 (요구사항에 맞게 수정)
        for row in data_rows:
            if is_total(row, address_indices):
                break

            if contains_invalid_keyword(row, price_indices, address_indices, area_indices):
                if current:
                    groups.append(current)
                    current = []
                for i in reversed(range(len(groups))):
                    if any(has_value(r, price_indices) for r in groups[i]):
                        groups[i] = sum(groups[i:], [])
                        groups[:] = groups[:i + 1]
                        break
                else:   # 지금까지 price 있는 행이 하나도 없었다
                    groups = []
                continue

            # 첫 행 처리
            if not current:
                current.append(row)
                continue

            # 감정평가액이 있는 그룹 다음에 오는 행, 일련번호가 있는 행도 새 그룹 시작
            if has_value(current[-1], price_indices) or has_value(row, serial_indices):
                groups.append(current)
                current = [row]

            # 그 외 경우 현재 그룹에 추가
            else:
                current.append(row)

        if current:
            groups.append(current)

    else:
        # 새 방식: 아래에서 위로 그룹화
        for row in data_rows:
            if is_total(row, address_indices):
                break

            if contains_invalid_keyword(row, price_indices, address_indices, area_indices):
                if current:
                    groups.append(current)
                    current = []
                for i in reversed(range(len(groups))):
                    if any(has_value(r, price_indices) for r in groups[i]):
                        groups[i] = sum(groups[i:], [])
                        groups[:] = groups[:i + 1]
                        break
                else:   # 지금까지 price 있는 행이 하나도 없었다
                    groups = []
                continue

            if has_value(row, serial_indices) or has_value(row, price_indices):
                groups.append(current + [row])
                current = []

            elif is_floor_info(row, structure_indices) and groups:
                groups[-1].append(row)

            else:
                current.append(row)

        if current:
            groups.append(current)
    
    # 행 병합
    merged_rows = []
    for group in groups:
        if not group:
            continue

        base_row = copy.deepcopy(group[0])
        min_y = min(cell["cell_bbox"][1] for row in group for cell in row["values"])
        max_y = max(cell["cell_bbox"][3] for row in group for cell in row["values"])

        for col_idx in range(len(base_row["values"])):
            ref_y_ranges = []
            for price_idx in price_indices:
                for row in group:
                    val = row["values"][price_idx]["value"]
                    if val.strip():
                        bbox = row["values"][price_idx]["cell_bbox"]
                        ref_y_ranges.append((bbox[1], bbox[3]))

            # 병합 텍스트 수집
            texts, texts_raw, text_bboxes, text_row_indices = [], [], [], []
            for row in group:
                if col_idx >= len(row["values"]):
                    continue
                cell = row["values"][col_idx]
                val = cell["value"].strip()
                if not val:
                    continue
                bbox = cell["cell_bbox"]
                row_idx = row["row_index"]
                if col_idx in area_indices:
                    # '사정' 컬럼은 감정평가액과 같은 y범위 내 값만 포함
                    if any(bbox[1] >= y1 and bbox[3] <= y2 for (y1, y2) in ref_y_ranges):
                        texts.append(val)
                        texts_raw.extend(cell.get("text", []))
                        text_bboxes.extend(cell.get("text_bbox", []))
                        text_row_indices.extend([row_idx] * len(cell.get("text", [])))
                else:
                    texts.append(val)
                    texts_raw.extend(cell.get("text", []))
                    text_bboxes.extend(cell.get("text_bbox", []))
                    text_row_indices.extend([row_idx] * len(cell.get("text", [])))

            merged_cell = base_row["values"][col_idx]
            if texts:
                if col_idx in property_indices:
                    merged_cell["value"] = ", ".join(dict.fromkeys(texts))
                else:
                    # 중복 제거 없이 병합
                    merged_cell = base_row["values"][col_idx]
                    merged_cell["value"] = " ".join(texts)
            else:
                merged_cell["value"] = ""

            merged_cell["text"] = texts_raw
            merged_cell["text_bbox"] = text_bboxes
            merged_cell["cell_bbox"][1] = min_y
            merged_cell["cell_bbox"][3] = max_y
            merged_cell["row_indices"] = text_row_indices

        base_row["column_header"] = False
        merged_rows.append(base_row)

    # 감정평가액이 없는 행의 '면적-사정' 셀 값 제거
    if len(area_indices) >= 1:
        sajeong_idx = area_indices[0]   # NOTE 다 없애야하지 않을까
        for row in merged_rows:
            has_price = has_value(row, price_indices)
            if not has_price and sajeong_idx < len(row["values"]):
                cell = row["values"][sajeong_idx]
                cell["value"] = ""
                cell["text"] = []
                cell["text_bbox"] = []
                cell["row_indices"] = []

    # 최종 테이블
    data["table"] = [{k: v for k, v in row.items() if k != "row_index"} for row in header_rows + merged_rows]

    print(f"행 병합 완료: {rows_len}개 행 → {len(merged_rows)}개 병합 행")

    return data


def merge_by_serial(input_path, oid):
    """테이블 처리 메인 함수"""
    try:
        # 데이터 로드 및 처리
        data = load_json(input_path)
        
        # 행 병합 처리
        return group_and_merge_rows(data, oid)

    except Exception as e:
        print(f"행 병합 처리 중 오류 발생: {str(e)}")
        return None

if __name__ == "__main__":
    input_path = "/home/dami/workspace/행나누기/명세표_0425/05.pts_json/0616042_0021_00_pts2.json"
    output_path = "/home/dami/workspace/행나누기/명세표_0425/05.pts_json/0616042_0021_00_pts_merged2.json"

    # input_path = "/home/dami/workspace/행나누기/명세표_0425/05.pts_json/1443002_0021_00_pts.json"
    # output_path = "/home/dami/workspace/행나누기/명세표_0425/05.pts_json/1443002_0021_00_pts_merged.json"
    
    merge_by_serial(input_path, output_path)