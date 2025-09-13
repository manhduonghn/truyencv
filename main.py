import requests
import json
import os
from urllib.parse import urlparse
from pathlib import Path
import re

# Thư mục lưu trữ nội dung
OUTPUT_DIR = "downloaded_content"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/manhduonghn/truyencv/main"
DOWNLOADED_URLS_FILE = os.path.join(OUTPUT_DIR, "downloaded_urls.json")

def load_downloaded_urls():
    """Tải danh sách URL đã tải từ tệp downloaded_urls.json"""
    try:
        if os.path.exists(DOWNLOADED_URLS_FILE):
            with open(DOWNLOADED_URLS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading downloaded_urls.json: {e}")
        return {}

def save_downloaded_urls(url_map):
    """Lưu danh sách URL đã tải vào tệp downloaded_urls.json"""
    try:
        Path(DOWNLOADED_URLS_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(DOWNLOADED_URLS_FILE, 'w', encoding='utf-8') as f:
            json.dump(url_map, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving downloaded_urls.json: {e}")

def is_valid_json(content):
    """Kiểm tra xem nội dung có phải là JSON hợp lệ không"""
    try:
        json.loads(content)
        return True
    except json.JSONDecodeError:
        return False

def download_file(url, output_path):
    """Tải nội dung từ URL và lưu vào tệp nếu chưa tồn tại và là JSON hợp lệ"""
    if os.path.exists(output_path):
        print(f"Skipping {url}: File already exists at {output_path}")
        return True
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = response.text
        if not content or not is_valid_json(content):
            print(f"Skipping {url}: Content is empty or not valid JSON")
            return False
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
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

def remove_unwanted_keys(json_data):
    """Loại bỏ related_providers, notice và các mục liên quan khỏi JSON"""
    if isinstance(json_data, dict):
        # Xóa các khóa liên quan đến related_providers và notice
        filtered_data = {
            key: remove_unwanted_keys(value)
            for key, value in json_data.items()
            if key not in ['related_providers', 'notice']
        }
        # Xóa các mục trong groups có chứa remote_data.url liên quan đến provider
        if 'groups' in filtered_data:
            filtered_data['groups'] = [
                group for group in filtered_data['groups']
                if not (
                    'remote_data' in group and
                    isinstance(group['remote_data'], dict) and
                    'url' in group['remote_data'] and
                    'type=provider' in group['remote_data']['url']
                )
            ]
        return filtered_data
    elif isinstance(json_data, list):
        return [remove_unwanted_keys(item) for item in json_data]
    return json_data

def crawl_load_more(base_url, total_pages, url_map):
    """Tải toàn bộ nội dung từ load_more, bỏ qua nếu đã tải"""
    for page in range(1, total_pages + 1):
        page_url = f"{base_url}?page={page}"
        if page_url in url_map:
            print(f"Skipping {page_url}: Already downloaded")
            continue
        output_path = os.path.join(OUTPUT_DIR, f"channels/page_{page}.json")
        if download_file(page_url, output_path):
            try:
                # Đọc và xóa related_providers, notice từ trang vừa tải
                with open(output_path, 'r', encoding='utf-8') as f:
                    page_data = json.load(f)
                page_data = remove_unwanted_keys(page_data)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(page_data, f, ensure_ascii=False, indent=2)
                url_map[page_url] = f"{GITHUB_RAW_BASE}/{output_path}"
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON in {output_path}: {e}")
                os.remove(output_path)  # Xóa tệp không hợp lệ
    return url_map

def main():
    # URL chính của JSON
    main_url = "https://truyenx.link/truyensextv"
    load_more_base_url = "https://truyenx.link/truyensextv/channels"
    
    # Tải danh sách URL đã tải
    url_map = load_downloaded_urls()

    # Tải JSON chính để lấy thông tin load_more
    main_output_path = os.path.join(OUTPUT_DIR, "main.json")
    if main_url not in url_map:
        try:
            response = requests.get(main_url, timeout=10)
            response.raise_for_status()
            json_data = response.json()

            # Lấy thông tin load_more
            load_more = json_data.get('load_more', {})
            page_info = load_more.get('pageInfo', {})
            total_pages = page_info.get('last_page', 1)

            # Tạo thư mục lưu trữ
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            # Tải toàn bộ nội dung từ load_more trước
            url_map = crawl_load_more(load_more_base_url, total_pages, url_map)

            # Loại bỏ related_providers và notice
            json_data = remove_unwanted_keys(json_data)

            # Lưu JSON chính
            with open(main_output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            url_map[main_url] = f"{GITHUB_RAW_BASE}/{main_output_path}"
        except Exception as e:
            print(f"Error processing main URL {main_url}: {e}")
            return
    else:
        print(f"Skipping {main_url}: Already downloaded")
        try:
            with open(main_output_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing main.json: {e}")
            return

    # Tải nội dung từ các liên kết trong JSON
    def crawl_urls(data, base_path=""):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == 'url' and isinstance(value, str) and value.startswith('http'):
                    if value in url_map:
                        print(f"Skipping {value}: Already downloaded")
                        continue
                    parsed_url = urlparse(value)
                    file_name = re.sub(r'[^\w\-_\.]', '_', parsed_url.path.strip('/')) + '.json'
                    output_path = os.path.join(OUTPUT_DIR, base_path, file_name)
                    if download_file(value, output_path):
                        try:
                            # Xóa related_providers và notice từ tệp vừa tải
                            with open(output_path, 'r', encoding='utf-8') as f:
                                sub_data = json.load(f)
                            sub_data = remove_unwanted_keys(sub_data)
                            with open(output_path, 'w', encoding='utf-8') as f:
                                json.dump(sub_data, f, ensure_ascii=False, indent=2)
                            url_map[value] = f"{GITHUB_RAW_BASE}/{output_path}"
                        except json.JSONDecodeError as e:
                            print(f"Error parsing JSON in {output_path}: {e}")
                            os.remove(output_path)  # Xóa tệp không hợp lệ
                else:
                    crawl_urls(value, base_path)
        elif isinstance(data, list):
            for item in data:
                crawl_urls(item, base_path)

    # Duyệt JSON để tìm tất cả các URL còn lại
    crawl_urls(json_data)

    # Thay thế URL trong JSON chính
    updated_json = replace_urls_in_json(json_data, url_map)

    # Lưu JSON đã cập nhật
    with open(main_output_path, 'w', encoding='utf-8') as f:
        json.dump(updated_json, f, ensure_ascii=False, indent=2)

    # Lưu danh sách URL đã tải
    save_downloaded_urls(url_map)

if __name__ == "__main__":
    main()
