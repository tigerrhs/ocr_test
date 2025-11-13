import json
from onbid.table_utils import generate_unique_id, convert_to_pdf_coords

def process_appraisal_info(appraisal_info, result, page_sizes, rotate, scale):
    '''감정평가 기관, 날짜 및 감정평가사 이름 정보를 처리'''

    # appraisal_agency 정보 처리
    appraisal_agency = appraisal_info.get("appraisal_agency")
    if appraisal_agency:
        # 좌표 변환 처리
        page_height = appraisal_agency.get("page_size", {}).get("height", 0)
        name_bbox = appraisal_agency["name"]["page_bbox"][0]["bbox"]
        name_bbox = convert_to_pdf_coords(name_bbox, page_height, scale)
        branch_bbox = appraisal_agency["branch"]["page_bbox"][0]["bbox"]
        branch_bbox = convert_to_pdf_coords(branch_bbox, page_height, scale)

        result["appraisal_agency"] = {
            "name": {
                "id": generate_unique_id(),
                "text": appraisal_agency["name"]["text"],
                "page_bbox": [
                    {
                        "page_num": appraisal_agency["name"]["page_bbox"][0]["page_num"] + 1,
                        "bbox": name_bbox
                    }
                ]
            },
            "branch": {
                "id": generate_unique_id(),
                "text": appraisal_agency["branch"]["text"],
                "page_bbox": [
                    {
                        "page_num": appraisal_agency["branch"]["page_bbox"][0]["page_num"] + 1,
                        "bbox": branch_bbox
                    }
                ]
            }
        }
        rotate_bbox_list(result["appraisal_agency"]["name"]["page_bbox"], page_sizes, rotate)
        rotate_bbox_list(result["appraisal_agency"]["branch"]["page_bbox"], page_sizes, rotate)

    # appraisal_date 정보 처리
    appraisal_date = appraisal_info.get("appraisal_date")
    if appraisal_date:
        # 좌표 변환 처리
        page_height = appraisal_date.get("page_size", {}).get("height", 0)
        original_bbox = appraisal_date["page_bbox"][0]["bbox"]
        converted_bbox = convert_to_pdf_coords(original_bbox, page_height, scale)
        
        result["appraisal_date"] = {
            "id": generate_unique_id(),
            "text": appraisal_date["text"],
            "page_bbox": [
                {
                    "page_num": appraisal_date["page_bbox"][0]["page_num"] + 1,
                    "bbox": converted_bbox
                }
            ]
        }
        rotate_bbox_list(result["appraisal_date"]["page_bbox"], page_sizes, rotate)

    # appraiser_name 정보 처리
    appraiser_name = appraisal_info.get("appraiser_name")
    if appraiser_name:
        # 좌표 변환 처리
        page_height = appraiser_name.get("page_size", {}).get("height", 0)
        original_bbox = appraiser_name["page_bbox"][0]["bbox"]
        converted_bbox = convert_to_pdf_coords(original_bbox, page_height, scale)

        result["appraiser_name"] = {
            "id": generate_unique_id(),
            "text": appraiser_name["text"],
            "page_bbox": [
                {
                    "page_num": appraiser_name["page_bbox"][0]["page_num"] + 1,
                    "bbox": converted_bbox
                }
            ]
        }
        rotate_bbox_list(result["appraiser_name"]["page_bbox"], page_sizes, rotate)

def create_final_json(appraisal_info, price_info, page_sizes, output_file, doc_id, original_file_path, fig_image_path, scale, rotate, oid):
    '''결과 JSON 형식을 생성하는 함수'''

    result = {
        "oid": oid,
        "doc_id": doc_id,
        "origin_pdf_path": original_file_path,
        # "text_pdf_path": text_pdf_path,
        "image_paths": [{'id': generate_unique_id(), 'path': image} for image in fig_image_path],
        "appraisal_agency": {},
        "appraiser_name": {},
        "appraisal_date": {},
        "location": [{'id': generate_unique_id(), **thing} for thing in price_info],
    }

    # 기관 및 날짜 정보 처리
    process_appraisal_info(appraisal_info, result, page_sizes, rotate, scale)

    for loc in result["location"]:
        for field in ("address_base", "address_dong", "address_floor_room", "address_type", "price", "property_usage", "area_m2"):
            rotate_bbox_list(loc[field]["page_bbox"], page_sizes, rotate)

    # 결과 저장
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def rotate_bbox_list(bboxes, page_sizes, rotate):
    for pb in bboxes:
        page_num = pb.get("page_num", 0) - 1
        if page_num in rotate:
            angle = rotate[page_num]
            bbox = pb["bbox"]
            if len(bbox) != 4:
                continue
            w, h = page_sizes[page_num]
            if angle == 90:
                pb["bbox"] = [h - bbox[3], bbox[0], h - bbox[1], bbox[2]]
            elif angle == 180:
                pb["bbox"] = [w - bbox[2], h - bbox[3], w - bbox[0], h - bbox[1]]
            elif angle == 270:
                pb["bbox"] = [bbox[1], w - bbox[2], bbox[3], w - bbox[0]]