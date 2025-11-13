import uuid
from pathlib import Path
import fitz  # PyMuPDF

def extract_text_with_coordinates(pdf_path, rotate, oid, doc_id):
    """
    PDF 파일에서 텍스트와 좌표 정보를 추출하여 JSON 형태로 반환
    
    Args:
        pdf_path (str): PDF 파일 경로
    
    Returns:
        dict: 추출된 텍스트와 좌표 정보가 담긴 딕셔너리
    """
    try:
        # PDF 파일 열기
        doc = fitz.open(pdf_path)
        
        # 파일명 추출 (확장자 제거하고 .json 추가)
        file_name = Path(pdf_path).stem + ".json"
        
        # 결과 구조 초기화
        result = {
            "oid": oid,
            "doc_id": doc_id,
            "file_name": file_name,
            "pages": []
        }
        
        # 각 페이지 처리
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # 페이지 크기 가져오기
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height
            
            # 페이지 정보 초기화
            page_info = {
                "page_num": page_num + 1,  # 1부터 시작
                "page_width": round(page_width, 3),
                "page_height": round(page_height, 3),
                "fields": []
            }
            
            # 텍스트 블록 추출 (좌표 포함)
            text_dict = page.get_text("dict")
            
            for block in text_dict["blocks"]:
                if "lines" in block:  # 텍스트 블록인 경우
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text:  # 빈 텍스트 제외
                                # 백슬래시를 원화 기호로 변환 (JSON 문제 방지)
                                text = text.replace("\\", "₩")
                                # 유니코드 대체 문자 제거 (인코딩 오류로 생성되는 문자)
                                text = text.replace("�", "")

                                bbox = span["bbox"]
                                
                                # 좌표 정보 (PDF 좌표계: 왼쪽 하단이 원점)
                                # PyMuPDF는 왼쪽 상단을 원점으로 하므로 변환
                                x0, y0, x1, y1 = bbox
                                bbox = [x0, page_height - y1, x1, page_height - y0]
                                bbox = [round(x, 3) for x in bbox]

                                if page_num in rotate:
                                    angle = rotate[page_num]
                                    if angle == 90:
                                        pdf_bbox = [y0, x0, y1, x1]
                                    elif angle == 180:
                                        pdf_bbox = [page_width - x1, y0, page_width - x0, y1]
                                    elif angle == 270:
                                        pdf_bbox = [page_height - y1, page_width - x1, page_height - y0, page_width - x0]
                                else:
                                    pdf_bbox = bbox
                                
                                
                                field_info = {
                                    "id": str(uuid.uuid4()),
                                    "text": text,
                                    "bbox": pdf_bbox,
                                    "json_bbox": bbox
                                }
                                
                                page_info["fields"].append(field_info)
            
            result["pages"].append(page_info)
        
        doc.close()
        return result
        
    except Exception as e:
        print(f"PDF 처리 중 오류 발생: {e}")
        return None

def movable_text_pdf_json(input_pdf_path, rotate, oid, doc_id):
    """
    PDF 파일을 처리하여 JSON 파일로 변환
    
    Args:
        input_pdf_path (str): 입력 PDF 파일 경로
    """
    # 텍스트와 좌표 추출
    extracted_data = extract_text_with_coordinates(input_pdf_path, rotate, oid, doc_id)
    
    if extracted_data is None:
        print("PDF 처리에 실패했습니다.")
        return
    
    # 결과 요약 출력
    # total_fields = sum(len(page["fields"]) for page in extracted_data["pages"])
    # print(f"\n처리 완료:")
    # print(f"- 총 페이지 수: {len(extracted_data['pages'])}")
    # print(f"- 추출된 텍스트 필드 수: {total_fields}")
    
    return extracted_data