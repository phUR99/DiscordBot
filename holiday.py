import requests
import json
from dotenv import load_dotenv
import os
import datetime
import xmltodict


def is_holiday():
    load_dotenv()
    service_key = os.getenv("API_KEY")
    url = (
        "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
    )
    now_year = datetime.datetime.now().strftime("%Y")
    now_month = datetime.datetime.now().strftime("%m")
    target_date_str = datetime.datetime.now().strftime("%Y%m%d")
    params = {
        "serviceKey": service_key,
        "solYear": now_year,
        "solMonth": now_month,
    }
    response = requests.get(url, params=params)
    decoded_xml = response.content.decode("utf-8")
    xml_dict = xmltodict.parse(decoded_xml)
    json_data = json.loads(json.dumps(xml_dict, ensure_ascii=False, indent=4))
    holiday_dates = [
        item["locdate"] for item in json_data["response"]["body"]["items"]["item"]
    ]
    return target_date_str in holiday_dates


if __name__ == "__main__":
    print(is_holiday())
