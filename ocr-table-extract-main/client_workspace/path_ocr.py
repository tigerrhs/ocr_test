# -*- coding: utf-8 -*-
# first change
# second change
import json
import requests
import os

address = "http://localhost:5001"

def tocr_request(oid, input_file, save_path, property_type):
    '''서버 파일 사용'''
    data = {'oid': oid, 'pdfPath': input_file, 'savePath': save_path, 'propertyType': property_type}

    res = requests.post(address+'/path-ocr', json=data, verify=False)
    if res.ok:
        response = json.loads(res.content)
        print(response['resultCode'])
        print(response['resultMessage'])
        if response['resultCode'] == 'E000':
            print(response['savePath'])
    else:
        print(res.text.encode('utf-8'))

if __name__ == "__main__":
    data_folder = "/mnt/d/ocr/onbid/data"
    savePath = "/mnt/d/OCR/onbid/upload_data"
    oid = "abc"
    results = os.listdir(savePath)
    pdf_files = os.listdir(data_folder)
    for i in range(len(pdf_files)):
        try:
            print(f"{len(pdf_files)} 파일 중 {i + 1}번째 파일 작업 실행 중입니다.")
            print("현재 작업중인 파일 :: " , pdf_files[i])
            inpath = f'{data_folder}/{pdf_files[i]}'
            tocr_request(oid + str(i), inpath, savePath, 'immovable')

        except Exception as e :
            print(e)