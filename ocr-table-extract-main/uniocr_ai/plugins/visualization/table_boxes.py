import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

from common_module import load_json

def visualize_table_boxes(image_path, json_path, output_path):
    """
    테이블과 (선택적) OCR 박스를 시각화하여 저장합니다.
    """
    # 이미지 로드
    img = Image.open(image_path)
    img_width, img_height = img.size

    # DPI 설정 (예: 100)
    dpi = 100
    figsize = (img_width / dpi, img_height / dpi)
    
    # JSON 로드        
    data = load_json(json_path)

    # 시각화 시작
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.imshow(img)
    
    # 테이블 bbox 그리기 (빨강=헤더, 파랑=일반)
    for row in data["table"]:
        is_header = row.get("column_header", False)
        color = 'red' if is_header else 'blue'
    
        for cell in row["values"]:
            bbox = cell.get("cell_bbox", cell.get("bbox"))
            x1, y1, x2, y2 = bbox
            width = x2 - x1
            height = y2 - y1
            rect = patches.Rectangle((x1, y1), width, height, linewidth=1.5,
                                     edgecolor=color, facecolor='none')
            ax.add_patch(rect)

            for tb in cell.get("text_bbox", []):
                tx1, ty1, tx2, ty2 = tb
                twidth = tx2 - tx1
                theight = ty2 - ty1
                text_rect = patches.Rectangle(
                    (tx1, ty1), twidth, theight, linewidth=1,
                    edgecolor='green', facecolor='none', linestyle='--'
                )
                ax.add_patch(text_rect)
    
    # 시각화 범위 설정
    ax.set_xlim([0, img.width])
    ax.set_ylim([img.height, 0])  # y축 반전
    ax.axis('off')
    
    # 결과 저장
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()  # 메모리 해제
    
    print(f"시각화 결과가 {output_path}에 저장되었습니다.")


def visualize_merged_table1(image_path, merged_structure, output_path, page):
    # 이미지 로드
    img = Image.open(image_path)
    img_width, img_height = img.size

    # DPI 설정 (예: 100)
    dpi = 100
    figsize = (img_width / dpi, img_height / dpi)

    # 시각화 시작
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.imshow(img)

    for line in merged_structure:
        for cell in line:
            for c in cell['cell']:
                if c['page'] == page and c['cell_bbox']:
                        bbox = c['cell_bbox']
                        x1, y1, x2, y2 = bbox
                        width = x2 - x1
                        height = y2 - y1
                        rect = patches.Rectangle((x1, y1), width, height, linewidth=1.5, edgecolor='blue', facecolor='none')
                        ax.add_patch(rect)
    
    # 시각화 범위 설정
    ax.set_xlim([0, img.width])
    ax.set_ylim([img.height, 0])  # y축 반전
    ax.axis('off')
    
    # 결과 저장
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()  # 메모리 해제
    
    print(f"시각화 결과가 {output_path}에 저장되었습니다.")


def visualize_merged_table2(image_path, json_path, page):
    # 이미지 로드
    img = Image.open(image_path)
    img_width, img_height = img.size

    # DPI 설정 (예: 100)
    dpi = 100
    figsize = (img_width / dpi, img_height / dpi)

    # JSON 로드        
    data = load_json(json_path)['location']

    # 시각화 시작
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.imshow(img)

    for location in data:
        color = random_color_generator()
        for feature in location:
            for box in location[feature]['page_bbox']:
                if box['page_num'] == page + 1:
                    tx1, ty1, tx2, ty2 = box['bbox']
                    twidth = tx2 - tx1
                    theight = ty2 - ty1
                    text_rect = patches.Rectangle(
                        (tx1, ty1), twidth, theight, linewidth=1,
                        edgecolor=color, facecolor='none', linestyle='--'
                    )
                    ax.add_patch(text_rect)
    
    # 시각화 범위 설정
    ax.set_xlim([0, img.width])
    ax.set_ylim([img.height, 0])  # y축 반전
    ax.axis('off')
    
    # 결과 저장
    plt.tight_layout()
    plt.savefig(image_path)
    plt.close()  # 메모리 해제
    
    print(f"시각화 결과가 {image_path}에 저장되었습니다.")

import random
 
def random_color_generator():
    r = random.randint(0, 200) / 255
    g = random.randint(0, 200) / 255
    b = random.randint(0, 200) / 255
    return (r, g, b)

if __name__ == "__main__":
    import json
    def load_json(file_path):
        '''JSON 파일을 로드하는 함수'''
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)

    image_path = r"D:\OCR\onbid\ocr-table-extract\data/5401026_0023.png"
    json_path = r"D:\OCR\onbid\ocr-table-extract\uniocr_ai\Source\TableStructure\jsons\2025\05\28\15/0926002_0000_00_pts.json"
    output_path = r"D:\OCR\onbid\ocr-table-extract\uniocr_ai\Source\TableStructure\jsons\2025\05\28\15/0926002_0000_00_pts.png"
    
    visualize_table_boxes(
        image_path=image_path,
        json_path=json_path,
        output_path=output_path,
    )