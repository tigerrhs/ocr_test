from onbid.table_utils import SAME_KEYWORDS, copy_field, extract_land_and_dong, merge_cells_info

# 동 패턴 정규표현식
# SAME_HORIZONTAL_LINE = 5  # 같은 줄로 판단하는 Y좌표 차이 임계값
# VERTICAL_GAP = 15
# HORIZONTAL_GAP = 20

# def get_price_y_center(row, group_indices):
#     """해당 행의 감정평가액 Y 중앙값 계산"""
#     if "감정평가액" not in group_indices:
#         return None
    
#     price_cells = get_cells_from_row(row, group_indices["감정평가액"], True)
#     if not price_cells:
#         return None
    
#     y_values = []
#     for cell in price_cells:
#         bbox = cell.get("text_bbox", [])
#         if bbox and len(bbox) == 4:
#             y_center = (bbox[1] + bbox[3]) / 2
#             y_values.append(y_center)
    
#     return sum(y_values) / len(y_values) if y_values else None

# def get_group_y_center(group):
#     """그룹의 Y 중앙값 계산"""
#     y_values = []
#     for cell in group:
#         bbox = cell.get("text_bbox", [])
#         if bbox and len(bbox) == 4:
#             y_center = (bbox[1] + bbox[3]) / 2
#             y_values.append(y_center)
    
#     return sum(y_values) / len(y_values) if y_values else None

# def find_closest_group_to_price(text_groups, data_rows, group_indices, row_idx):
#     """
#     주어진 행의 감정평가액 Y좌표와 가장 가까운 그룹을 전체 그룹 중에서 선택
#     단, 현재 행(row_idx)에 속한 셀을 포함한 그룹만 비교 대상으로 사용
#     """
#     price_y = get_price_y_center(data_rows[row_idx], group_indices)
#     if price_y is None:
#         return None
    
#     closest_group = None
#     min_distance = float('inf')
    
#     for group in text_groups:
#         # 현재 행(row_idx)에 포함된 셀이 하나라도 있는 그룹만 처리
#         if not any(cell.get("row_index") == row_idx for cell in group):
#             continue

#         group_y = get_group_y_center(group)
#         if group_y is not None:
#             distance = abs(group_y - price_y)
#             # if distance <= tolerance and distance < min_distance:
#             if distance < min_distance:
#                 min_distance = distance
#                 closest_group = group

#     return closest_group


# def extract_dong_pattern_from_group(group):
#     """
#     그룹에서 동 패턴 추출 (도로명 주소용)
#     - "동"으로 끝나는 패턴을 찾되, 같은 줄에 있는 텍스트만 결합
#     - 여러 행에 걸쳐 있을 경우 동이 포함된 줄만 처리
#     - 결과는 그룹의 가장 위 행에 할당됨 (호출하는 쪽에서 처리)
#     """
    
#     if not group:
#         return "", []

#     # 1단계: 동 패턴이 있는 셀들 찾기
#     dong_cells = []
#     for cell in group:
#         text = cell.get("text", "").strip()
#         if re.search(DONG_PATTERN, text):
#             dong_cells.append(cell)
    
#     if not dong_cells:
#         return "", []

#     # 2단계: 동이 있는 셀들의 Y좌표를 기준으로 같은 줄 셀들만 필터링
#     dong_y_coords = [cell.get("text_bbox", [0, 0, 0, 0])[1] for cell in dong_cells]
#     avg_dong_y = sum(dong_y_coords) / len(dong_y_coords)
    
#     same_line_cells = []
#     for cell in group:
#         cell_y = cell.get("text_bbox", [0, 0, 0, 0])[1]
#         if abs(cell_y - avg_dong_y) <= SAME_HORIZONTAL_LINE:
#             same_line_cells.append(cell)

#     # 3단계: 같은 줄 셀들을 X좌표 순으로 정렬하여 텍스트 결합
#     same_line_cells.sort(key=lambda c: c.get("text_bbox", [0, 0, 0, 0])[0])            

#     # 4단계: 결합된 텍스트에서 동 패턴 추출
#     full_text = "".join(cell.get("text", "").strip() for cell in same_line_cells)
#     matches = list(DONG_PATTERN.finditer(full_text))
    
#     if not matches:
#         return "", []
    
#     # 첫 번째 매칭된 동 패턴 사용
#     match = matches[0]
#     matched_text = match.group().strip()
    
#     # 5단계: 매칭된 텍스트의 위치에 해당하는 셀들의 bbox 정보 수집
#     char_to_cell_index = []
#     for cell_idx, cell in enumerate(same_line_cells):
#         text = cell.get("text", "").strip()
#         char_to_cell_index.extend([cell_idx] * len(text))
    
#     # 매칭된 텍스트의 셀 위치 찾기
#     start_char = match.start()
#     end_char = match.end() - 1
    
#     page_bbox = []
#     if start_char < len(char_to_cell_index) and end_char < len(char_to_cell_index):
#         # 매칭된 텍스트에 해당하는 셀들의 bbox 수집
#         used_cells = set()
#         for char_idx in range(start_char, end_char + 1):
#             if char_idx < len(char_to_cell_index):
#                 cell_idx = char_to_cell_index[char_idx]
#                 if cell_idx not in used_cells and cell_idx < len(same_line_cells):
#                     used_cells.add(cell_idx)
#                     page_bbox.append({
#                         "page_num": same_line_cells[cell_idx].get("page", 0) + 1,
#                         "bbox": same_line_cells[cell_idx].get("text_bbox")
#                     })
    
#     return matched_text, page_bbox


def find_earliest_row_in_group(group):
    """그룹에 속한 셀들 중 가장 빠른 행 번호를 찾기"""
    row_indices = [cell.get('row_index') for cell in group['cell']]
    return min(row_indices) if row_indices else -1


def assign_lot_to_rows(text_groups, location_entries):
    """
    지번 그룹들을 분석하고 각 행에 할당할 지번 정보를 결정
    - 감정평가액 Y 중심값 기준 가장 가까운 그룹만 사용하고, 중복 사용 안함
    """
    row_assignments = {}
    for group in text_groups:
        # 이 그룹이 속한 가장 빠른 행 찾기
        earliest_row = find_earliest_row_in_group(group)
        if earliest_row == -1 or earliest_row not in location_entries:
            continue

        # 그냥 이 그룹을 바로 할당 (가장 먼저 나오는 group 기준)
        if earliest_row not in row_assignments: # 이미 행할당 되어있으면 넘어감
            row_assignments[earliest_row] = group

    # 기존 로직: 감정평가액과 가장 가까운 그룹을 사용 (단, 아직 사용되지 않은 그룹만)
    # target_row = earliest_row
    # closest_group = find_closest_group_to_price(text_groups, data_rows, group_indices, target_row)
    # closest_group이 현재 group과 동일한 경우만 사용
    # if closest_group is group:
    #     merged_text, page_bbox = merge_group_cells_info(group)
    #     if merged_text:
    #         row_assignments[target_row] = (merged_text, page_bbox)

    return row_assignments


def check_road_address(address_map, key_num, entry, land_group):
    location = entry["address_base"]["text"].replace(' ', '')
    lands, dongs = land_group['lands'], land_group['dongs']

    candidates = list()
    if address_map and location:
        if key_num == 2:
            for land in lands:
                candidates.extend(address_map.get((location, land), []))
        else:
            for land in lands:
                for dong in dongs:
                    candidates.extend(address_map.get((location, land, dong), []))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    candidates = list({item["index"]: item for item in candidates}.values())    # 중복 제거

    location_index = entry["address_base"]["index"]
    for road_addr in candidates:
        if location_index <= road_addr['index'] <= location_index + 1:   # 지번 주소의 짝인 도로명 주소
            return road_addr
    
    prev_candidates = [road_addr for road_addr in candidates if road_addr['index'] < location_index]    # 이전에 나온 도로명 주소
    if prev_candidates:
        return max(prev_candidates, key=lambda a: a['index'])

    # 뒤에 나오는 도로명 주소 중 가장 빠른 것
    return min(candidates, key=lambda a: a['index'])


def process_lot_number_field(text_groups, location_entries, address_map, key_num):
    """모든 행의 지번 필드를 한번에 처리"""
    # 그룹 분석 및 행별 할당
    row_assignments = assign_lot_to_rows(text_groups, location_entries)

    # 각 행에 지번 정보 할당
    prev_entry = None
    for row_idx, location_entry in location_entries.items():
        location = location_entry["address_base"]["text"]
        if row_idx in row_assignments:  # 해당 행에 할당된 지번 정보가 있음
            land_group = row_assignments[row_idx]
            land_text, page_bbox = merge_cells_info(land_group['cell'])
            location_entry["address_dong"]["page_bbox"] = page_bbox

            if any(keyword in land_text for keyword in SAME_KEYWORDS):
                location_entry["address_dong"]["text"] = prev_entry["address_dong"]["text"]
                continue

            road_address = check_road_address(address_map, key_num, location_entry, land_group)
            change_address(location_entry, road_address, land_group)

        elif prev_entry and location == prev_location:
            # 이전 행에서 복사 가능한지 판단, 소재지가 같을 경우에만 복사
            copy_field(prev_entry, location_entry, "address_base")
            copy_field(prev_entry, location_entry, "address_type")
            copy_field(prev_entry, location_entry, "address_dong")

        prev_location = location
        prev_entry = location_entry


def retain_land_groups(land_groups):
    new_groups = list()
    for cells in land_groups:
        lands, dongs = extract_land_and_dong(cells)
        if not lands:
            continue
        group = {
            'cell': cells,
            'rows': [cell['row_idx'] for cell in cells],
            'lands': lands,
            'dongs': dongs,
            'page': cells[0]['page']
        }
        new_groups.append(group)
    
    land_groups[:] = new_groups


def change_address(entry, road_addr, land_group):
    del entry["address_base"]["index"]
    if road_addr:
        entry["address_base"]["text"] = road_addr["text"]
        _, entry["address_base"]["page_bbox"] = merge_cells_info(road_addr["bbox"])
        entry["address_dong"]["text"] = ", ".join(land_group['dongs'])
        if not entry["address_dong"]["text"]:
            entry["address_dong"]["page_bbox"] = ""
        entry["address_type"]["text"] = "도로명"
        entry["address_type"]["page_bbox"] = entry["address_base"]["page_bbox"]
    else:
        entry["address_dong"]["text"] = ", ".join(land_group['lands'])