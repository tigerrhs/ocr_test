def title_table_to_html(table_data):
    '''"column_header": true 인 줄 전체에 배경색 적용해서 HTML 테이블 시각화'''
    cell_map = {}
    max_row = 0
    max_col = 0

    for row_idx, row in enumerate(table_data):
        for col_idx, cell in enumerate(row):
            if isinstance(cell, str):  # 문자열인 경우 (헤더)
                text = cell.strip()
            elif isinstance(cell, dict):
                text = cell.get("merged_text", "").strip()
                if not text and "cell" in cell:
                    text = " ".join(c.get("text", "").strip() for c in cell["cell"] if c.get("text"))
            else:
                text = ""

            cell_map[(row_idx, col_idx)] = {
                "text": text,
                "row_nums": [row_idx],
                "column_nums": [col_idx],
            }

            max_row = max(max_row, row_idx)
            max_col = max(max_col, col_idx)

    html = ['<table border="1" cellspacing="0" cellpadding="4">']

    style = ' style="background-color:pink;"'
    for r in range(max_row + 1):
        html.append('  <tr>')
        for c in range(max_col + 1):
            cell = cell_map.get((r, c))
            if cell and "rendered" in cell:
                continue

            value = cell["text"]
            html.append(f'    <td{style}>{value}</td>')

            cell["rendered"] = True  # 중복 렌더 방지
        html.append('  </tr>')
        style = ''
    html.append('</table>')

    return '\n'.join(html)