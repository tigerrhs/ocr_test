from common_module import load_json

def final_info_html(json_path):
    json_data = load_json(json_path)

    agency_name = None
    branch_name = None
    name = None
    date = None

    if json_data["appraisal_agency"]:
        agency_name = json_data["appraisal_agency"]["name"]["text"]
        branch_name = json_data["appraisal_agency"]["branch"]["text"]

    if json_data["appraiser_name"]:
        name = json_data["appraiser_name"]["text"]

    if json_data["appraisal_date"]:
        date = json_data["appraisal_date"]["text"]

    html = f'''<table border="1">
  <thead>
    <tr>
      <th>감정평가기관</th>
      <th>지사명</th>
      <th>평가사</th>
      <th>평가일자</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>{agency_name}</td>
      <td>{branch_name}</td>
      <td>{name}</td>
      <td>{date}</td>
    </tr>
  </tbody>
</table>'''

    html += '''
<table border="1">
  <thead>
    <tr>
      <th>주소</th>
      <th>동</th>
      <th>층호</th>
      <th>체계</th>
      <th>용도</th>
      <th>면적 (㎡)</th>
      <th>가격</th>
    </tr>
  </thead>
  <tbody>
'''

    # 데이터 반복 처리
    for item in json_data["location"]:
        address_base = item["address_base"]["text"]
        address_dong = item["address_dong"]["text"]
        area = item["area_m2"]["text"]
        usage = item["property_usage"]["text"]
        price = item["price"]["text"]

        html += f'''    <tr>
      <td>{address_base}</td>
      <td>{address_dong}</td>
      <td>{item["address_floor_room"]["text"]}</td>
      <td>{item["address_type"]["text"]}</td>
      <td>{usage}</td>
      <td>{area}</td>
      <td>{price}</td>
    </tr>
'''

    # HTML 테이블 종료
    html += '''  </tbody>
</table>'''

    with open(json_path.replace('.json', '.html'), "w", encoding="utf-8") as f:
        f.write(html)

    print(json_path.replace('.json', '.html') + ' 저장됨')