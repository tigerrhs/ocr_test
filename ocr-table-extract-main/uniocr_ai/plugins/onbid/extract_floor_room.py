import re
from onbid.table_utils import get_cells_from_row, make_text_groups, FLOOR_PATTERN, ROOM_PATTERN

def nae_at(text):
    """'(내)' 패턴의 위치를 찾는 함수"""
    nae_patterns = ["(내)", "내)", "(내", "[내]", "내]", "[내"]
    for nae in nae_patterns:
        if nae in text:
            return text.find(nae) + len(nae)
    return -1

def find_group_with_nae_pattern(group):
    """그룹에서 (내) 패턴이 있는지 확인"""
    group_text = "".join(cell.get("text", "") for cell in group)
    return nae_at(group_text) >= 0

def has_floor_room_pattern(group):
    """그룹에서 층/호 패턴이 모두 있는지 확인"""
    full_text = "".join(cell.get("text", "").replace(" ", "") for cell in group)
    
    floor_match = FLOOR_PATTERN.search(full_text)
    room_match = ROOM_PATTERN.search(full_text)
    
    # 층과 호가 모두 있어야 True 반환
    return floor_match is not None and room_match is not None

def extract_floor_room_from_group(group, start_char=0):
    """그룹에서 층/호 패턴을 추출"""
    if not group:
        return [], []

    # 전체 문자열 만들고, 문자별 셀 인덱스를 저장
    full_text = ""
    char_to_cell_index = []

    for cell_idx, cell in enumerate(group):
        text = cell.get("text", "")
        char_to_cell_index.extend([cell_idx] * len(text))
        full_text += text.replace(" ", "")

    # start_char 이후의 텍스트에서 패턴 찾기
    search_text = full_text
    search_offset = 0
    if start_char > 0:
        search_text = full_text[start_char:]
        search_offset = start_char

    texts = []
    page_bbox = []

    # 1. 층 패턴 찾기
    floor_match = FLOOR_PATTERN.search(search_text)
    if not floor_match:
        return [], []  # 층이 없으면 빈 결과 반환
    
    # 2. 층 이후 텍스트에서 호 패턴 찾기
    floor_end_in_search = floor_match.end()
    after_floor_text = search_text[floor_end_in_search:]
    
    # 호 패턴을 층 이후 텍스트에서만 찾기 (공백 제거 후)
    room_match = ROOM_PATTERN.search(after_floor_text)

    if not room_match:
        return [], []  # 호가 없으면 빈 결과 반환

    # 3. 층 정보 추출
    floor_start_in_full = search_offset + floor_match.start()
    floor_end_in_full = search_offset + floor_match.end() - 1
    
    if (floor_start_in_full < len(char_to_cell_index) and 
        floor_end_in_full < len(char_to_cell_index)):
        
        start_cell_idx = char_to_cell_index[floor_start_in_full]
        end_cell_idx = char_to_cell_index[floor_end_in_full]

        texts.append(floor_match.group())
        
        for cell_idx in range(start_cell_idx, end_cell_idx + 1):
            if cell_idx < len(group):
                page_bbox.append({
                    "page_num": group[cell_idx].get("page", 0) + 1, 
                    "bbox": group[cell_idx].get("text_bbox")
                })

    # 4. 호 정보 추출 (공백 제거된 매칭 결과 사용)
    actual_room_text = room_match.group(1)  # 공백 제거된 호 텍스트
    room_start_in_search = floor_end_in_search + room_match.start(1)
    room_end_in_search = floor_end_in_search + room_match.end(1) - 1
    
    room_start_in_full = search_offset + room_start_in_search
    room_end_in_full = search_offset + room_end_in_search
    
    if (room_start_in_full < len(char_to_cell_index) and 
        room_end_in_full < len(char_to_cell_index)):
        
        start_cell_idx = char_to_cell_index[room_start_in_full]
        end_cell_idx = char_to_cell_index[room_end_in_full]

        texts.append(actual_room_text)
        
        for cell_idx in range(start_cell_idx, end_cell_idx + 1):
            if cell_idx < len(group):
                page_bbox.append({
                    "page_num": group[cell_idx].get("page", 0) + 1, 
                    "bbox": group[cell_idx].get("text_bbox")
                })
        
    return texts, page_bbox

def find_earliest_row_in_group(group, row_cells):
    """그룹에 속한 셀들 중 가장 빠른 행 번호를 찾기"""
    earliest_row = float('inf')
    
    for group_cell in group:
        for row_idx, cells in enumerate(row_cells):
            for cell in cells:
                # 같은 셀인지 확인 (페이지, 좌표, 텍스트로 비교)
                if (cell.get("page") == group_cell.get("page") and
                    cell.get("text_bbox") == group_cell.get("text_bbox") and
                    cell.get("text") == group_cell.get("text")):
                    earliest_row = min(earliest_row, row_idx)
                    break
    
    return earliest_row if earliest_row != float('inf') else -1

def analyze_groups_and_assign_to_rows(text_groups, row_cells):
    """
    그룹들을 분석하고 각 행에 할당할 층/호 정보를 결정
    반환값: {row_idx: (texts, page_bbox)} 형태의 딕셔너리
    """
    row_assignments = {}
    
    for group in text_groups:
        has_nae = find_group_with_nae_pattern(group)
        has_floor_room = has_floor_room_pattern(group)
        
        if not has_floor_room:
            continue  # 층과 호 패턴이 모두 없으면 스킵
        
        # 이 그룹이 속한 가장 빠른 행 찾기
        target_row = find_earliest_row_in_group(group, row_cells)
        
        if target_row == -1:
            continue
        
        if has_nae:
            # (내) 패턴이 있으면 (내) 이후 텍스트에서 층/호 추출
            group_text = "".join(cell.get("text", "") for cell in group)
            start_char = nae_at(group_text)
            texts, page_bbox = extract_floor_room_from_group(group, start_char)
        else:
            # (내) 패턴이 없으면 전체에서 층/호 추출
            texts, page_bbox = extract_floor_room_from_group(group)
        
        if texts:
            row_assignments[target_row] = (texts, page_bbox)
    
    return row_assignments

def process_usage_region_field(data_rows, group_indices, location_entries):
    """모든 행의 용도지역및구조 필드를 한번에 처리"""
    
    if "용도지역및구조" not in group_indices:
        return
    
    # 1. 전체 그룹 생성
    text_groups, row_cells = make_text_groups(data_rows, group_indices["용도지역및구조"])
    
    # 2. 그룹 분석 및 행별 할당
    row_assignments = analyze_groups_and_assign_to_rows(text_groups, row_cells)
    
    # 3. 각 행에 층/호 정보 할당
    for row_idx, location_entry in location_entries.items():
        if row_idx in row_assignments:
            # 해당 행에 할당된 층/호 정보가 있음
            texts, page_bbox = row_assignments[row_idx]
            location_entry["address_floor_room"]["text"] = " ".join(texts)
            location_entry["address_floor_room"]["page_bbox"] = page_bbox
        else:
            # 할당된 정보가 없으면 현재 행의 셀에서 직접 확인
            current_cells = get_cells_from_row(data_rows[row_idx], group_indices["용도지역및구조"], True)
            if has_floor_room_pattern(current_cells):
                texts, page_bbox = extract_floor_room_from_group(current_cells)
                if texts:
                    location_entry["address_floor_room"]["text"] = " ".join(texts)
                    location_entry["address_floor_room"]["page_bbox"] = page_bbox