'''
@Time    :   February 1, 2026
@Author  :   JINXI LV
@Contact :   ljx331@gmail.com
===============================================
SJTU Thesis Crawler 2026版
目前仅支持单论文按标题检索下载
仅供学习交流使用！！！
'''
import json
import sys
import os
import time
from pathlib import Path
from urllib.parse import quote
import shutil
import img2pdf
import requests
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import concurrent.futures

SAVE_DIR = "raw_pages_jpg"
FINAL_PDF_DIR = "./papers"
os.makedirs(FINAL_PDF_DIR, exist_ok=True)
TOTAL_PAGES_EXPECTED = 500
SEARCH_TYPE_DEFAULT = "题名"
XUEWEI = "0"
PX = "2"


def search_paper(keyword, search_type=SEARCH_TYPE_DEFAULT):
    choose_key_map = {
        '主题': 'topic', '题名': 'title', '关键词': 'keyword', '作者': 'author',
        '院系': 'department', '专业': 'subject', '导师': 'teacher', '年份': 'year'
    }
    key = choose_key_map.get(search_type, 'title')
    base_url = (
        f"http://thesis.lib.sjtu.edu.cn/sub.asp?"
        f"content={quote(keyword)}"
        f"&choose_key={key}"
        f"&xuewei={XUEWEI}"
        f"&px={PX}"
        f"&page=1"
    )
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(base_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"搜索页状态码异常：{resp.status_code}")
            return None
        tree = etree.HTML(resp.content)
        try:
            title = tree.xpath('/html/body/section/div/div[3]/div[2]/table/tr[2]//td[2]/text()')[0].strip()
            author = tree.xpath('/html/body/section/div/div[3]/div[2]/table/tr[2]/td[3]/div/text()')[0].strip()
            mentor = tree.xpath('/html/body/section/div/div[3]/div[2]/table/tr[2]/td[6]/div/text()')[0].strip()
            year = tree.xpath('/html/body/section/div/div[3]/div[2]/table/tr[2]/td[8]/div/text()')[0].strip()
            link = "http://thesis.lib.sjtu.edu.cn/" + \
                   tree.xpath('/html/body/section/div/div[3]/div[2]/table/tr[2]/td[9]/div/a[2]/@href')[0]

            paperid = link.split("paperid=")[1].split("&")[0]
            print(f"找到匹配论文：{title} ({year}) 作者：{author}")
            return {
                'title': title,
                'author': author,
                'mentor': mentor,
                'year': year,
                'link': link,
                'paperid': paperid
            }
        except IndexError:
            print("未找到任何结果，或页面结构变化")
            return None
    except Exception as e:
        print(f"搜索失败：{e}")
        return None


def get_fid_from_link(driver, detail_link):
    driver.get(detail_link)
    current_url = driver.current_url
    if "fid=" in current_url:
        fid = current_url.split("fid=")[1].split("&")[0].split("#")[0]
        return fid


def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    driver = webdriver.Chrome(options=options)
    return driver


def extract_image_urls_from_logs(driver):
    logs = driver.get_log("performance")
    image_urls = set()
    for entry in logs:
        try:
            msg = json.loads(entry['message'])['message']
            if msg['method'] == 'Network.responseReceived':
                url = msg['params'].get('response', {}).get('url', '')
                if 'P01_' in url and url.endswith('.jpg'):
                    image_urls.add(url)
        except:
            continue
    return sorted(image_urls)


def download_images(image_urls, driver, save_dir, max_workers=8):
    if os.path.exists(save_dir):
        shutil.rmtree(save_dir)
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    cookies = {c['name']: c['value'] for c in driver.get_cookies()}
    headers = {
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Referer": "http://thesis.lib.sjtu.edu.cn:8443/read/pdfindex.jsp",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    downloaded = 0
    failed_urls = []

    def download_single(url):
        nonlocal downloaded
        try:
            r = requests.get(url, headers=headers, cookies=cookies, timeout=15, verify=False)
            if r.status_code == 200 and len(r.content) > 5000:
                filename = url.split('/')[-1]
                path = Path(save_dir) / filename
                path.write_bytes(r.content)
                downloaded += 1
                return True, url
            else:
                print(f"页面{url}状态异常无法下载")
                return False, url
        except Exception as e:
            print(f"下载异常 {url}: {e}")
            return False, url
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(download_single, url): url for url in image_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            success, url = future.result()
            if not success:
                failed_urls.append(url)
    if failed_urls:
        print(f"\n有 {len(failed_urls)} 张下载失败，重试一次...")
        for url in failed_urls:
            success, _ = download_single(url)
            if success:
                downloaded += 1
    print(f"DOWNLOADED：SUCCESS {downloaded} / {len(image_urls)} PAGES")
    return downloaded


def merge_to_pdf(save_dir, output_pdf):
    jpg_files = list(Path(save_dir).glob("P01_*.jpg"))
    if not jpg_files:
        print("没有找到 jpg 文件，无法合并")
        return

    jpg_files.sort(key=lambda p: int(p.stem.split('_')[1]))
    print(f"MERGING {len(jpg_files)} PAGES TO PDF...")
    try:
        with open(output_pdf, "wb") as f:
            f.write(img2pdf.convert([str(p) for p in jpg_files]))
        print(f"PDF → {output_pdf}")
    except Exception as e:
        print(f"合并失败: {e}")


def load_all_pages_by_click(driver):
    max_clicks = TOTAL_PAGES_EXPECTED + 20
    successful_clicks = 0
    previous_page = 0
    spinner = ['-', '\\', '|', '/']
    for attempt in range(max_clicks):
        try:
            next_btn = driver.find_element(By.ID, "btnnext")
            if not next_btn.is_displayed() or not next_btn.is_enabled():
                print("\n下一页按钮不可见或禁用，疑似已到末页")
                break
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
            next_btn.click()
            time.sleep(0.5)
            successful_clicks += 1
            bar_length = 20
            filled = (successful_clicks // 5) % (bar_length + 1)
            bar = '█' * filled + '░' * (bar_length - filled)
            spin_char = spinner[successful_clicks % 4]
            sys.stdout.write(f'\rLOADING... [{bar}] PAGES {successful_clicks}   {spin_char}')
            sys.stdout.flush()
            try:
                current_page_input = driver.find_element(By.ID, "textpagenum")
                current_page = int(current_page_input.get_attribute("value"))
                if current_page == previous_page:
                    break
                previous_page = current_page
            except:
                pass

            if successful_clicks >= TOTAL_PAGES_EXPECTED - 1:
                break
        except Exception as e:
            print(f"\n点击失败 (尝试 {attempt + 1})：{str(e)}")
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a[title='下一页']")
                next_btn.click()
                time.sleep(2.0)
            except:
                print("备用定位也失败，结束翻页循环")
                break
    sys.stdout.write('\r' + ' ' * 80 + '\r')
    sys.stdout.flush()
    if previous_page > 0:
        print(f"TOTAL PAGES：{previous_page}")


def main():
    keyword = input("请输入论文题目：").strip()
    if not keyword:
        print("BYE")
        return
    if os.path.exists(SAVE_DIR):
        shutil.rmtree(SAVE_DIR)
    os.makedirs(SAVE_DIR, exist_ok=True)
    paper_info = search_paper(keyword)
    if not paper_info:
        print("搜索无结果或失败")
        return
    driver = setup_driver()
    try:
        ENTRANCE_STEPS = [
            "http://thesis.lib.sjtu.edu.cn/",
            "http://thesis.lib.sjtu.edu.cn/sub.asp",
            paper_info['link'],
        ]
        for url in ENTRANCE_STEPS:
            driver.get(url)
        fid = get_fid_from_link(driver, paper_info['link'])
        if not fid:
            print("无法获取 fid")
            return
        pdfindex_url = f"http://thesis.lib.sjtu.edu.cn:8443/read/pdfindex.jsp?fid={fid}"
        driver.get(pdfindex_url)
        print("ACCESSING...")
        load_all_pages_by_click(driver)
        image_urls = extract_image_urls_from_logs(driver)
        if not image_urls:
            print("未捕获到图片 URL，尝试 fallback 方式...")
            try:
                store_prefix = driver.execute_script("return document.getElementById('sm_img_url').value;")
                print(f"从页面获取 store 前缀: {store_prefix}")
                image_urls = [
                    f"http://thesis.lib.sjtu.edu.cn:8443/read/store/{store_prefix}/P01_{i:05d}.jpg"
                    for i in range(1, TOTAL_PAGES_EXPECTED + 1)
                ]
            except:
                print("无法获取 store 前缀，下载失败")
                return
        downloaded_count = download_images(image_urls, driver, SAVE_DIR, max_workers=8)
        if downloaded_count > 0:
            pdf_name = f"{paper_info['year']}_{paper_info['title']}_{paper_info['author']}.pdf"
            pdf_path = os.path.join(FINAL_PDF_DIR, pdf_name)
            merge_to_pdf(SAVE_DIR, pdf_path)
        else:
            print("下载失败，没有图片")
    finally:
        driver.quit()
        print("FINISHED!\nBYE")


if __name__ == "__main__":
    main()