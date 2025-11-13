import json
import requests
import time
import shutil
from common_module import write_log
from configs import etc_config


OLLAMA_IP = etc_config['OLLAMA_IP']

def correct_spelling_with_ollama(text, oid, model="llama3.2-korean:latest"):
    """
    Ollama API를 사용하여 텍스트의 오타를 교정합니다.
    
    Args:
        text (str): 교정할 텍스트
        model (str): 사용할 Ollama 모델 이름
        
    Returns:
        str: 교정된 텍스트
    """
    prompt = f"""
오타가 없다면 원문 그대로 출력하고, 맞춤법이 틀렸다면 교정된 문장만 출력해줘.  
한국어로만 대답해줘
*설명이나 추가 멘트 없이 결과만 출력해줘.

텍스트: "{text}"
"""
    
    # try:
    response = requests.post(f'http://{OLLAMA_IP}:11434/api/generate', 
                            json={
                                "model": model,
                                "prompt": prompt,
                                "stream": False
                            })
    
    if response.status_code == 200:
        corrected = response.json()['response'].strip()
        
        
        # 불필요한 따옴표 제거
        if corrected.startswith('"') and corrected.endswith('"'):
            corrected = corrected[1:-1]
        
        # "교정된 텍스트는 다음과 같습니다:" 같은 접두어 제거
        prefixes = [
            "교정된 텍스트는 다음과 같습니다:",
            "교정된 텍스트:",
            "교정된 텍스트는 ",
            "교정 결과:"
        ]
        
        for prefix in prefixes:
            if corrected.startswith(prefix):
                corrected = corrected[len(prefix):].strip()
        
        # 남아있는 \n 제거
        corrected = corrected.strip("\n")
        
        return corrected
    else:
        write_log(f"API 오류: {response.status_code}, {response.text}", etc_config['LOG_LEVEL_ERROR'], oid)
        return text
    # except Exception as e:
    #     print(f"오류 발생: {e}")
    #     return text


def find_and_correct_all_text_keys(data, model, oid):
    """
    JSON 데이터에서 모든 "text" 키를 재귀적으로 찾아 오타를  교정합니다.
    
    Args:
        data: JSON 데이터 (딕셔너리 또는 리스트)
        model (str): 사용할 Ollama 모델 이름

    Returns:
        동일한 구조에 "text" 키의 값이 교정된 데이터
    """

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "text" and isinstance(value, str):
                original_text = value
                corrected_text = correct_spelling_with_ollama(original_text, model)
                data[key] = corrected_text
                write_log(f"[LLAMA POSTPRO] before : {original_text} , after :{corrected_text}",etc_config['LOG_LEVEL_INFO'], oid)
                
            elif isinstance(value, (dict, list)):
                find_and_correct_all_text_keys(value, model, oid)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                find_and_correct_all_text_keys(item, model, oid)
 
    
    return data

def post_process_json_file(input_file, output_file, oid, model="llama3.2-korean:latest"):
    """
    JSON 파일에서 모든 "text" 키의 값의 오타를 교정합니다.
    
    Args:
        input_file (str): 입력 JSON 파일 경로
        output_file (str): 출력 JSON 파일 경로
        model (str): 사용할 Ollama 모델 이름
    """
    # JSON 파일 읽기
    # 이전 json 파일 우선 백업
    shutil.copyfile(input_file , input_file.replace(".json" ,"_bu.json"))
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    write_log(f"JSON 파일 분석 완료. 모든 'text' 키를 찾아 교정합니다...", etc_config['LOG_LEVEL_INFO'], oid)

    # 재귀적으로 모든 "text" 키를 찾아 교정
    corrected_data = find_and_correct_all_text_keys(data, model, oid)
    
    # 결과 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(corrected_data, f, ensure_ascii=False, indent=2)
    
    write_log(f"처리 완료. 결과가 {output_file}에 저장되었습니다.", etc_config['LOG_LEVEL_INFO'], oid)

if __name__ == "__main__":
    # 사용자 입력 받기
    #input_file =  r"C:\Users\LEGION\Desktop\scan\image\p2202304388A020000012025\미래새한_mini.json" # input("입력 JSON 파일 경로를 입력하세요: ")
    input_file =  "/mnt/c/Users/LEGION/Desktop/scan/image/p2202304388A020000012025/미래새한_mini.json" # input("입력 JSON 파일 경로를 입력하세요: ")
    output_file = input_file.replace(".json","") + "_ollama.json"
    
    # 모델 선택 (기본값 제공)
    model =  "llama3.2-korean:latest"
    
    print(f"\n사용 모델: {model}")
    
    # llama_postpro.py 실행 시, post_process_json_file의 oid 인자를 oid=None으로 설정해야한다.
    post_process_json_file(input_file, output_file, model)
