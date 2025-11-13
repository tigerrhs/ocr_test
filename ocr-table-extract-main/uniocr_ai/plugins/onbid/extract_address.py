import re
from collections import defaultdict

from common_module import write_log
from configs import etc_config
from onbid.table_utils import is_bbox_overlap, state_city, STOPWORDS, SAME_KEYWORDS, ROAD_ADDRESS_WORDS

# 도로명주소 패턴 정규표현식
ROAD_ADDRESS_PATTERN = re.compile("|".join(map(re.escape, ROAD_ADDRESS_WORDS)))
# 도로명주소 끝 패턴 추가 (예: '월산로 111-48' 형태로 숫자가 포함된 주소 이후 종료)
ROAD_ADDRESS_END_PATTERN = re.compile(r'로\s?\d+(-\d+)?|(번?길)\s?\d+(-\d+)?')

def address_row_text_groups(text_groups, row_cells):
    # 각 행과 겹치는 그룹 찾기
    row_text_groups = []
    for i, rowcell in enumerate(row_cells):
        matching_groups = []
        for group in text_groups:
            if i not in group['merged_rows']:
                continue
            for cell in rowcell:
                if cell['page'] == group['cell'][0]['page'] and is_bbox_overlap(cell["cell_bbox"], group['bboxes']):
                    matching_groups.append(group)
                    break

        row_text_groups.append(matching_groups)
    return row_text_groups


def start_address(text):
    match = re.search(f"({state_city})", text)
    if match:
        return text[match.start():]
    return ''


def clean_address(text):
    # 텍스트 clean
    text = start_address(text)
    if not text:
        return text
    pattern = '|'.join(map(re.escape, STOPWORDS + SAME_KEYWORDS + ROAD_ADDRESS_WORDS))
    text = re.sub(pattern, '', text).strip()
    if (m := re.search('대지권의', text)):
        text = text[:m.start()]

    return text


def process_location_groups(location_groups):
    text_groups = []
    for cells in location_groups:
        """주소 텍스트 정리"""
        address_text = ""
        char_to_index = []

        # 텍스트 정리 및 인덱스 생성
        for i, cell in enumerate(cells):
            text = cell["text"]
            if i != 0 and cells[i - 1]["row_idx"] != cell["row_idx"]: # 줄이 바뀜
                text = ' ' + text
            char_to_index.extend([i] * len(text))
            address_text += text

        text_bboxes = [cell["text_bbox"] for cell in cells]
        if text_bboxes:
            min_x = min(b[0] for b in text_bboxes)
            min_y = min(b[1] for b in text_bboxes)
            max_x = max(b[2] for b in text_bboxes)
            max_y = max(b[3] for b in text_bboxes)
        group = {
            'text': address_text,
            'cell': cells,
            'bboxes': (min_x, min_y, max_x, max_y),
            'merged_rows': set(cell["row_index"] for cell in cells if cell.get("row_index") is not None),   # 내가 포함되는 금액 행
            'rows': [cell["row_idx"] for cell in cells]  # merged row 말고 한 줄에 한 글자
        }
        text_groups.append(group)

    return text_groups


def build_address_map(location_groups, land_groups, last_location, oid):
    """소재지랑 지번 컬럼은 무조건 붙어있다고 보는 상태"""
    addr_jibun_to_road_3key = defaultdict(list)

    for i, group in enumerate(location_groups):
        # 소재지 컬럼에서 도로명 주소 찾고, 그 위의 지번 주소 저장
        group['index'] = i
        text = group['text'].replace('「', '').replace('［', '').replace('」', '').replace('］', '')
        match = ROAD_ADDRESS_PATTERN.search(text)
        if match:
            location = ''
            road_address = {
                'index': i,
                'text': text[match.end():].strip(),
                'page': group['cell'][0]['page'],   # 어차피 같은 페이지에서만 그룹됨
                'bbox': group['cell']
            }
            text = text[:match.start()]

            if text:
                if same_with_last(text) and last_location:    # 동소 + [도로명주소]
                    group['point'] = last_location
                    location = last_location['text']
                else:
                    location = clean_address(text)
                    if location:
                        last_location = group
                    group['text'] = location

                # 지번 주소와 도로명 주소가 한 그룹일 경우
                text_index = 0
                cells = group['cell']

                for j, cell in enumerate(cells):
                    cell_text = cell["text"]
                    if j != 0 and cells[j - 1]["row_idx"] != cell["row_idx"]: # 줄이 바뀜
                        cell_text = ' ' + cell_text
                    text_index += len(cell_text)
                    if text_index >= match.start():
                        group['cell'], road_address['bbox'] = group['cell'][:j], group['cell'][j:]
                        road_address['jibeon_line'] = group['rows'] = group['rows'][:j]   # 그룹에 지번주소만 남김
                        break

            if not location:
                for j in range(i - 1, -1, -1):  # 앞 그룹들 조사
                    prev_group = location_groups[j]
                    if 'point' in prev_group:
                        location = prev_group['point']['text']
                        road_address['jibeon_line'] = prev_group['rows']
                        break
                    else:
                        location = prev_group['text']
                        if location:
                            road_address['jibeon_line'] = prev_group['rows']
                            break
                else:
                    write_log(f"{road_address['text']}의 지번 주소가 안 보임", etc_config['LOG_LEVEL_ERROR'], oid)
                    road_address['jibeon_line'] = group['rows']
                group['text'] = ''

            land = None
            # 도로명 주소와 겹치는 지번 컬럼 저장
            road_line_set = set(road_address['jibeon_line'])
            for land_group in land_groups:
                if land_group['page'] == road_address['page'] and any(r in road_line_set for r in land_group['rows']): # 겹치면
                    land = land_group
                    break
                elif land_group['page'] == road_address['page'] and land_group['rows'][0] > road_address['jibeon_line'][-1] or land_group['page'] > road_address['page']: # ~도로명 범위에 지번 없으면
                    break
                land = land_group
            if not land:
                continue

            lands, dongs = land['lands'], land['dongs']
            if not dongs:
                dongs = [None]

            location = location.replace(' ', '')
            for land in lands:
                for dong in dongs:
                    addr_jibun_to_road_3key[(location, land, dong)].append(road_address)

        else:
            if same_with_last(text) and last_location:    # 동소
                group['point'] = last_location
            else:
                text = clean_address(text)
                if text:
                    last_location = group
                group['text'] = text

    location_groups[:] = [group for group in location_groups if group['text']]

    addr_jibun = defaultdict(set)
    addr_jibun_to_road_2key = defaultdict(list)
    for (loc, land, dong), roads in addr_jibun_to_road_3key.items():
        for road in roads:
            addr_jibun[(loc, land)].add(road['text'])
            addr_jibun_to_road_2key[(loc, land)].append(road)

    if all(len(roads) == 1 for roads in addr_jibun.values()):   # 동이 달라도 도로명 주소 안 바뀜
        return dict(addr_jibun_to_road_2key), 2, last_location
    
    return addr_jibun_to_road_3key, 3, last_location


def process_address(location_groups, last_location):
    """지번 컬럼 못 찾아서 소재지라도 정리"""
    address_map = dict()
    for i, group in enumerate(location_groups):
        text = group['text']
        match = ROAD_ADDRESS_PATTERN.search(text)
        if match:
            road_address = text[match.end():].replace('［', '').replace('］', '').strip()
            location = clean_address(text[:match.start()])
            address_map[location] = i
            group['text'] = road_address
            last_location = group

        else:
            if same_with_last(text) and last_location:    # 동소
                if last_location['text'] in address_map:    # last_location이 지번 주소
                    group['point'] = location_groups[address_map[last_location['text']]]
                else:
                    group['point'] = last_location

            else:
                text = clean_address(text)
                if text:
                    last_location = group
                group['text'] = text

    location_groups[:] = [group for group in location_groups if group['text']]
    return last_location


def select_address_group(location_groups, row_idx):
    for i in range(row_idx, -1, -1):
        for j in range(len(location_groups[i]) - 1, -1, -1):
            return location_groups[i][j]


def same_with_last(text):
    for keyword in SAME_KEYWORDS:
        if keyword in text:
            return keyword
    return None