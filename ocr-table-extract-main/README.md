# 📄 ocr-table-extract (OCR 테이블 추출)
- 업데이트 날짜: 2025.11.13
- ezPDF Workflow에 변환 요청 가능

<br />

## 💡 프로젝트 소개
- 온비드 감정평가문서를 OCR하여 감정평가정보 추출

<br />

## 🛠️ 구현 기능

propertyType: "immovable"(부동산)일 시

표와 사진 탐지(detectron): 페이지 이미지에서 명세표와 사진 탐지 후 저장

⬇️

UniOCR: PDF를 OCR하거나 기존 텍스트에 있는 텍스트 정보를 뽑아서 텍스트 PDF 파일 생성

⬇️

propertyType: "movable"(동산)일 시 savePath에 텍스트 PDF, OCR json 저장 후 경로 리턴 ⭐

propertyType: "immovable"(부동산)일 시

감정평가 정보 추출 (1): 표지와 감정평가표에서 감정평가기관, 감정평가일자, 감정평가사 정보추출

⬇️

표 구조 분석: 감정평가 명세표에서 TATR로 열 구분, OCR된 텍스트 좌표로 행 구분

⬇️

감정평가 정보 추출 (2): 감정평가 명세표에서 감정평가물의 소재지, 금액 등 감정평가 정보 추출

⬇️

후처리: sllm 또는 정규식으로 감정평가 일자, 감정평가 금액 후처리

⬇️

savePath에 최종 json 저장 후 경로 리턴 ⭐

<br />


## 파일 구조
```
📁 client_worksapce (클라이언트)
📁 uniocr_ai (서버)
📁 lea (패키지)
📁 unused
 ```

<br />


## 기능
| 기능 | O/X | 비고 |
|---------|-----|-----|
| 계정생성  | O | -|
| 로그인  | X | -|
| 이미지 기울기 보정  | O | -|
| 파일 내용 암/복호화  | O | -|
| 문서 구조 탐지 (표탐지)  | O | -|
| 표구조 인식  | O | -|
| sLLM   | O | llama3.2-korean 3B 모델|
| 커스터마이징   | O | 요구사항 추출(요구사항 정의서 확인)|

- OCR 방식: 이미지 텍스트만 제목OCR -> 제목 보고 필요 페이지 OCR
- PDF 생성방식: `pageObj['/Rotate']` 값이 있으면 `drawImage`하고 없으면 `pageObj` 저장
- 손상 PDF && 텍스트PDF && 일부 페이지가 이미지 페이지일 경우 원본에서 텍스트 정보 불러와서 metadata에 추가
<br />

## API REQUEST
- 암호화 X
- json으로 요청

### API
/path-ocr

### REQUEST JSON
```
{
  'oid': oid,
  'pdfPath': 감정평가서 문서 PDF 파일 경로,
  'savePath': 결과 JSON을 저장할 폴더 경로,
  'propertyType': 부동산 (immovable) / 부동산 외 (movable)
}
```
<br />

## 고객 환경 
- OS: redhat9
- CPU/GPU: CPU

<br />

## 💻 환경
- 패키징 환경: CentOS9-Stream (윈도우 WSL2 사용)

- torch
```
pip install torch==1.11.0+cpu torchvision==0.12.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu
```

- detectron
```
yum install gcc-c++ -y
git clone https://github.com/facebookresearch/detectron2.git
cd detectron2
pip install -e .
```

- 라이브러리 설치
```
cd uniocr_ai
pip install -r requirements.txt
```

- lea
```
cd lea
python setup.py install
```

- 추가 다운로드 파일
```
- NAS2:/01.Project/20250304_온비드OCR/04.Model/model_final_early_stop.pth
- NAS2:/01.Project/20250304_온비드OCR/04.Model/OCR_Model/
- NAS2:/01.Project/20250304_온비드OCR/04.Model/model71.pth
- NAS2:/01.Project/20250304_온비드OCR/04.Model/resnet.py
- NAS2:/01.Project/20250304_온비드OCR/ezPDF_CaptureAI/api-server/lice/
- NAS2:/01.Project/20250304_온비드OCR/04.Model/resnet18-f37072fd.pth

# 기존 resnet.py를 NAS2에서 받은 파일로 덮어쓰기
cp -f ./resnet.py /root/miniconda3/envs/onbid_cpu/lib/python3.8/site-packages/torchvision/models/
```
<br />

## 솔루션 제공 파일 NAS 위치
- NAS2:\01.Project\20250304_온비드OCR\97.패키징\패치1112,1112
<br />

## 최신패치날짜
2025.11.13

## 패키징 방법
1. 💻에 나온대로 환경을 세팅한다
2. `bulid_plugins.py`로 *.py를 *.gnu.so로 컴파일한다
3. `bin`에서 `strip --strip-unneeded plugins/*.so`
(전체 파일을 빌드했을 때는 모델 가중치 등 빠진 파일을 확인 필요)
3. `uniocr_ai`에서 `pyinstaller split.spec`으로 실행파일을 만든다.
4. `bin`의 `plugins`를 꺼내와서 다음과 같은 구조로 만든다.
```
📁 lice
📁 plugins (컴파일 한 거)
📁 resources
📄 config.ini
📄 entrypoint.txt
💾 uniocr
```
