import os
import time
import signal
import json
import zipfile
import urllib.request
import urllib.error
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================= 基础配置 =================
SERVER_URL = "https://panel.godlike.host/server/61b8ad3c"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"

SCREENSHOT_DIR = "screenshots"
SCREENSHOT_ZIP = "screenshots.zip"
TASK_TIMEOUT_SECONDS = 300

# ================= GitHub 配置 =================
REPO = os.environ.get("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_API = "https://api.github.com"
TAG = f"screenshots-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

if not GITHUB_TOKEN:
    raise RuntimeError("❌ 未检测到 GITHUB_TOKEN")

# ================= 超时控制 =================
class TaskTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行时间超过设定阈值")

if os.name != "nt":
    signal.signal(signal.SIGALRM, timeout_handler)

# ================= 工具函数 =================
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def take_screenshot(page, name):
    path = f"{SCREENSHOT_DIR}/{name}.png"
    page.screenshot(path=path)
    print(f"📸 截图: {path}", flush=True)
    return path

def zip_screenshots():
    if not os.path.isdir(SCREENSHOT_DIR):
        return
    files = os.listdir(SCREENSHOT_DIR)
    if not files:
        return
    with zipfile.ZipFile(SCREENSHOT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(os.path.join(SCREENSHOT_DIR, f), arcname=f)
    print(f"📦 已生成 {SCREENSHOT_ZIP}", flush=True)

# ================= Godlike 登录（非 headless） =================
def login_with_playwright(page):
    cookie = os.environ.get("PTERODACTYL_COOKIE")
    if not cookie:
        raise Exception("未提供 PTERODACTYL_COOKIE")

    page.context.add_cookies([{
        "name": COOKIE_NAME,
        "value": cookie,
        "domain": ".panel.godlike.host",
        "path": "/",
        "httpOnly": True,
        "secure": True,
        "sameSite": "Lax",
    }])

    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(3000)
    take_screenshot(page, "01_after_open_server")

    # 处理 Authorization
    auth_span = page.locator('span:has-text("Authorization")')
    if auth_span.count() > 0:
        take_screenshot(page, "02_before_authorization")
        auth_span.locator("xpath=ancestor::button").click()

        print("🔑 已点击 Authorization，等待 OAuth 回跳...", flush=True)

        # 给 OAuth 足够时间（非常重要）
        for _ in range(30):  # 最多 150 秒
            time.sleep(5)
            if "/server/" in page.url:
                break
        else:
            take_screenshot(page, "AUTH_NOT_RETURNED_TO_SERVER")
            raise Exception("OAuth 未成功回到服务器页面")

        page.wait_for_timeout(3000)
        take_screenshot(page, "03_after_authorization")

    # 最终校验（硬性）
    if "/server/" not in page.url:
        take_screenshot(page, "LOGIN_FAILED_FINAL_CHECK")
        raise Exception("最终校验失败：仍未进入服务器面板")

# ================= 增加时长任务 =================
def add_time_task(page):
    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(5000)
    before_img = take_screenshot(page, "04_before_add_90_minutes")

    for _ in range(18):
        span = page.locator('span:has-text("Add 90 minutes")')
        if span.count() > 0:
            span.locator("xpath=ancestor::button").click()
            after_img = take_screenshot(page, "05_after_click_add_90_minutes")

            page.locator('button:has-text("Watch advertisment")').click()
            final_img = take_screenshot(page, "06_after_click_watch_ad")

            print("⏳ 等待 2 分钟...", flush=True)
            time.sleep(120)

            return [before_img, after_img, final_img]

        time.sleep(5)

    print("ℹ️ 当前不可加时（未出现 Add 90 minutes）", flush=True)
    skip_img = take_screenshot(page, "07_add_90_not_available")
    return [before_img, skip_img]

# ================= 主程序 =================
def main():
    ensure_dir(SCREENSHOT_DIR)

    with sync_playwright() as p:
        # 🔥 关键：非 headless + 反自动化参数
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US"
        )

        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            if os.name != "nt":
                signal.alarm(TASK_TIMEOUT_SECONDS)

            login_with_playwright(page)
            screenshots = add_time_task(page)

            if os.name != "nt":
                signal.alarm(0)

        except Exception:
            take_screenshot(page, "99_error")
            zip_screenshots()
            browser.close()
            raise

        finally:
            browser.close()

    zip_screenshots()

if __name__ == "__main__":
    main()
