import json
from onbid.table_utils import find_header_indices, mainheader_keyword

def concat_table(structure_path):
    """표 구조를 연결하면서 cell 구조 변환"""

    header_len = {group: 0 for group in mainheader_keyword}

    all_page = []
    all_header = []
    all_data = []

    for json_file in structure_path:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_page.append(data['page_num'])
            table = data['table']

        header_rows = list()
        data_rows = list()

        for row in table:
            if row.get("column_header"):
                header_rows.append(row)
            else:
                data_rows.append(row)

        if not all_header:  # 첫 파일
            first_columns_num = len(header_rows[0]['values'])

        if all_header and first_columns_num == len(header_rows[0]['values']):  # 첫 파일과 컬럼 개수 같음
            header_indices = {group: indices.copy() for group, indices in all_header[0].items()}

        else:   # 첫 파일이거나 컬럼 개수 다름
            header_indices = find_header_indices(header_rows)

            for group, indices in header_indices.items():
                if len(indices) > header_len[group]:
                    header_len[group] = len(indices)

        # NOTE 현재 첫 페이지의 column header가 맞다고 생각하고 병합하고 있으나
        # 첫 페이지에 모든 column index가 추출이 안 되고 뒷 페이지에 추출될 경우 추가해야할 지 고려 필요

        all_header.append(header_indices)
        all_data.append(data_rows)

    column_name = []
    for group, indices in header_len.items():
        column_name += indices * [group]

    data_rows = []
    
    for page, header, data in zip(all_page, all_header, all_data):
        for row in data:
            new_row = []
            for group, indices in header_len.items():
                for _ in range(indices - len(header[group])):   # 남는 만큼
                    new_row.append({"merged_text": "", "cell": [{"text": "", "text_bbox": [], "cell_bbox": [], "page": page, "row_idx": None}]})
                for index in header[group]:
                    new_row.append(to_cell_structure(row['values'][index], page))
            data_rows.append(new_row)

    return column_name, data_rows


def to_cell_structure(value, page):
    """모든 셀을 새로운 구조로 변환 (value → merged_text + cells 구조)"""
    merged_text = value.get("value", "")
    texts = value.get("text", [])
    text_bboxes = value.get("text_bbox", [])
    row_indices = value.get("row_indices", [])
    bbox = value.get("cell_bbox", [0, 0, 0, 0])
    # 페이지 정보는 그대로 유지

    cell = []
    if value['text']:
        for idx in range(len(texts)):
            t = texts[idx]
            tb = text_bboxes[idx]
            ri = row_indices[idx]
            cell.append({
                "text": t,
                "text_bbox": tb,
                "cell_bbox": bbox,
                "page": page,
                "row_idx": ri
            })
    else:
        cell.append({
            "text": "",
            "text_bbox": [],
            "cell_bbox": bbox,
            "page": page,
            "row_idx": None
        })

    return {
        "merged_text": merged_text,
        "cell": cell
    }


if __name__ == "__main__":
    import os
    dir = '../Source/TableStructure/jsons/2025/06/04/test'

    structure = []
    json_files = [os.path.join(dir, f) for f in os.listdir(dir) if f.endswith('pts_merged.json')]
    for j in json_files:
        first = j == os.path.join(dir, '2922004_0045_00_pts_merged.json')
        structure = concat_table(structure, j, first)
    
    with open(os.path.join(dir, 'concat.json'), 'w', encoding='utf-8') as f:
        json.dump(structure, f, ensure_ascii=False)