import requests
import json
import os
from urllib.parse import urlparse
from pathlib import Path
import re

# Thư mục lưu trữ nội dung
OUTPUT_DIR = "downloaded_content"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main"

def download_file(url, output_path):
    """Tải nội dung từ URL và lưu vào tệp"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def replace_urls_in_json(json_data, url_map):
    """Thay thế các URL trong JSON bằng URL GitHub"""
    def replace_url(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ['url', 'remote_data', 'related', 'share'] and isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if subkey == 'url' and subvalue in url_map:
                            value[subkey] = url_map[subvalue]
                elif key == 'url' and value in url_map:
                    obj[key] = url_map[value]
                else:
                    replace_url(value)
        elif isinstance(obj, list):
            for item in obj:
                replace_url(item)

    replace_url(json_data)
    return json_data

def main():
    # URL chính của JSON
    main_url = "https://truyenx.link/truyensextv"
    
    # Tải JSON chính
    response = requests.get(main_url)
    response.raise_for_status()
    json_data = response.json()

    # Tạo thư mục lưu trữ
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Lưu trữ ánh xạ URL gốc sang URL GitHub
    url_map = {}

    # Lưu JSON chính
    main_output_path = os.path.join(OUTPUT_DIR, "main.json")
    with open(main_output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    url_map[main_url] = f"{GITHUB_RAW_BASE}/{main_output_path}"

    # Tải nội dung từ các liên kết trong JSON
    def crawl_urls(data, base_path=""):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == 'url' and isinstance(value, str) and value.startswith('http'):
                    # Tạo tên tệp từ URL
                    parsed_url = urlparse(value)
                    file_name = re.sub(r'[^\w\-_\.]', '_', parsed_url.path.strip('/')) + '.json'
                    output_path = os.path.join(OUTPUT_DIR, base_path, file_name)
                    if download_file(value, output_path):
                        url_map[value] = f"{GITHUB_RAW_BASE}/{output_path}"
                else:
                    crawl_urls(value, base_path)
        elif isinstance(data, list):
            for item in data:
                crawl_urls(item, base_path)

    # Duyệt JSON để tìm tất cả các URL
    crawl_urls(json_data)

    # Thay thế URL trong JSON chính
    updated_json = replace_urls_in_json(json_data, url_map)

    # Lưu JSON đã cập nhật
    with open(main_output_path, 'w', encoding='utf-8') as f:
        json.dump(updated_json, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
