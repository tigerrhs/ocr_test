import json
import re

def normalize_date_fields_in_json(input_file, output_file):
    """
    JSON 파일 'appraisal_date' 필드의 값을 ISO 포맷(YYYY-MM-DD)으로 정규화합니다.
    """
    def normalize_date_string(text):
        patterns = [r'(\d{4})[년\.\-\s]?(\d{1,2})[월\.\-\s]?(\d{1,2})']
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    yyyy, mm, dd = match.groups()
                    return f"{int(yyyy):04d}-{int(mm):02d}-{int(dd):02d}"
                except:
                    pass
        return text

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        modified = False

        if "appraisal_date" in data:
            original = data["appraisal_date"].get("text", "")
            formatted = normalize_date_string(original)
            if original != formatted:
                print(f"[DATE] 변경: {original} → {formatted}")
                data["appraisal_date"]["text"] = formatted
                modified = True

        if modified:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[DATE] 정규화 후 저장 완료: {output_file}")
        else:
            print("[DATE] 변경된 날짜 없음.")

    except Exception as e:
        raise RuntimeError(f"[normalize_date_fields_in_json] 오류: {str(e)}")


def normalize_price_fields_in_json(input_file, output_file):
    """
    JSON 파일 'price' 필드의 값을 천 단위 쉼표 형식으로 정규화합니다.
    """
    def normalize_price_string(text):
        try:
            clean_text = re.sub(r'[^\d]', '', text)
            if not clean_text:
                return text
            return f"{int(clean_text):,}"
        except:
            return text

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        modified = False

        if "location" in data:
            for i, loc in enumerate(data["location"]):
                price = loc.get("price", {})
                price_text = price.get("text", "")

                if isinstance(price_text, str):
                    formatted = normalize_price_string(price_text)
                    if price_text != formatted:
                        print(f"[PRICE] 변경: {price_text} → {formatted}")
                        loc["price"]["text"] = formatted
                        modified = True
        else:
            print("[PRICE] 'location' 키 없음")

        if modified:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[PRICE] 정규화 후 저장 완료: {output_file}")
        else:
            print("[PRICE] 변경된 가격 없음.")

    except Exception as e:
        raise RuntimeError(f"[normalize_price_fields_in_json] 오류: {str(e)}")
