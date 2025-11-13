from configs import ocr_config
import fitz  # PyMuPDF
import re
from configs import ocr_config

from tatr.join_text import group_rows_by_y


TOP_RATIO = float(ocr_config['TITLE_RATIO'])  # 상단 20% 영역만
Y_TOLERANCE = 5.0  # 라인 그룹핑 허용 오차

with open('./resources/평가표제목.txt', encoding='utf-8') as f:
    title_words = [line.strip() for line in f if line.strip()]
    summary_title_patterns = [
        re.compile(f".*?{word}.{{0,10}}", re.UNICODE)
        for word in title_words
    ]

with open('./resources/명세표제목.txt', encoding='utf-8') as f:
    title_words = [line.strip() for line in f if line.strip()]
    detail_title_patterns = [
        re.compile(f".*?{word}.{{0,10}}", re.UNICODE)
        for word in title_words
    ]


def extract_title_text(text, summary_possible, detail_possible):
    """텍스트에서 제목 패턴 추출"""
    text = re.sub(r'[^가-힣]', '', text)

    if summary_possible:
        for pattern in summary_title_patterns:
            match = pattern.search(text)
            if match:
                return text[:match.end()], "감정평가표"

    if detail_possible:
        for pattern in detail_title_patterns:
            match = pattern.search(text)
            if match:
                return text[:match.end()], "감정평가명세표"

    return '', None


def group_text_by_line(blocks, y_tolerance=Y_TOLERANCE):
    """같은 라인에 있는 텍스트 묶기"""
    blocks_sorted = sorted(blocks, key=lambda b: b[1])  # y0 기준 정렬
    lines = []
    current_line = []

    for block in blocks_sorted:
        x0, y0, x1, y1, text, *_ = block
        center_y = (y0 + y1) / 2

        if not current_line:
            current_line.append((x0, text))
            last_center_y = center_y
        else:
            y_diff = abs(center_y - last_center_y)
            if y_diff <= y_tolerance:
                current_line.append((x0, text))
            else:
                lines.append(current_line)
                current_line = [(x0, text)]
            last_center_y = center_y

    if current_line:
        lines.append(current_line)

    return lines


def filter_title_fields(page_data):
    height = page_data['PAGE_HEIGHT']
    return [field for field in page_data['FIELDS'] if field["FIELD_RELM"][1] + field["FIELD_RELM"][3] <= height * float(ocr_config['TITLE_RATIO'])]


def extract_page_title_pdf(page, summary_possible, detail_possible):
    """단일 페이지에서 제목 추출"""
    title_rect = fitz.Rect(0, 0, page.rect.width, page.rect.height * float(ocr_config['TITLE_RATIO']))
    text_blocks = page.get_text('blocks', clip=title_rect)

    if not text_blocks:
        return '', None

    # 블록들을 y좌표 기준으로 정렬해서 줄 단위로 병합
    lines = group_text_by_line(text_blocks)

    for line in lines:
        text = "".join([text for *_, text in sorted(line, key=lambda x: x[0])])
        title_text, title_type = extract_title_text(text, summary_possible, detail_possible)
        if title_text:
            return title_text, title_type
    
    return '', None


def extract_page_title_ocr(ocr_fields, summary_possible, detail_possible):
    """단일 페이지에서 제목 추출"""
    if not ocr_fields:
        return '', None

    # 블록들을 y좌표 기준으로 정렬해서 줄 단위로 병합
    lines = group_rows_by_y(ocr_fields, "OCR", Y_TOLERANCE)

    for line in lines:
        text = "".join([field['FIELD_TEXT'] for field in line])
        title_text, title_type = extract_title_text(text, summary_possible, detail_possible)
        if title_text:
            return title_text, title_type
    
    return '', None


def group_consecutive_pages(page_titles):
    """연속된 페이지에서 같은 제목끼리 그룹핑"""
    groups = []
    current_group = None

    for page_num, title_text in page_titles:
        if '기계기구' in title_text or '공작물' in title_text:
            continue
        # 새 그룹 시작 조건:
        # 1. 첫 번째 페이지
        # 2. 이전 페이지와 연속되지 않음 (페이지 번호 차이가 1보다 큼)
        # 3. 제목이 다름
        if (current_group is None or 
            page_num != current_group['last_page'] + 1 or
            title_text[:3] != current_group['text'][:3]):

            if current_group is not None:
                if title_text == '':    # 컬럼 키워드로 명세표 페이지 찾아냄
                    current_group['last_page'] = page_num
                    continue

                # 이전 그룹 완료
                groups.append({
                    'text': current_group['text'],
                    'page_range': [current_group['start_page'], current_group['last_page']]
                })

            # 새 그룹 시작
            current_group = {
                'text': title_text,
                'start_page': page_num,
                'last_page': page_num
            }
        else:
            # 현재 그룹에 페이지 추가
            current_group['last_page'] = page_num

    # 마지막 그룹 추가
    if current_group is not None:
        groups.append({
            'text': current_group['text'],
            'page_range': [current_group['start_page'], current_group['last_page']]
        })
    return groups


def text_in_content(page):
    content_rect = fitz.Rect(0, page.rect.height * float(ocr_config['TITLE_RATIO']), page.rect.width, page.rect.height)
    return bool(page.get_text(clip=content_rect))