import os
import time
import signal
import zipfile
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================= 配置 =================
SERVER_URL = "https://panel.godlike.host/server/61b8ad3c"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"

SCREENSHOT_DIR = "screenshots"
SCREENSHOT_ZIP = "screenshots.zip"
TASK_TIMEOUT_SECONDS = 300

# ================= 超时控制 =================
class TaskTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行时间超过设定阈值")

if os.name != "nt":
    signal.signal(signal.SIGALRM, timeout_handler)

# ================= 工具 =================
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def shot(page, name):
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

# ================= 登录（仅 OAuth，非 headless） =================
def login(page):
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
    shot(page, "01_open_server")

    auth = page.locator('span:has-text("Authorization")')
    if auth.count() > 0:
        shot(page, "02_before_authorization")
        auth.locator("xpath=ancestor::button").click()
        print("➡️ 点击 Authorization", flush=True)

    # 等待真正进入 server 页面
    for _ in range(30):
        time.sleep(2)
        if "/server/" in page.url:
            shot(page, "03_after_authorization")
            print("✅ OAuth 登录成功", flush=True)
            return

    shot(page, "LOGIN_FAILED")
    raise Exception("OAuth 登录失败（未进入 server 页面）")

# ================= 增加时长 =================
def add_time(page):
    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(5000)
    shot(page, "04_before_add_90_minutes")

    btn = page.locator('span:has-text("Add 90 minutes")')
    if btn.count() == 0:
        print("ℹ️ 当前不可加时", flush=True)
        shot(page, "05_add_not_available")
        return

    btn.locator("xpath=ancestor::button").click()
    shot(page, "06_after_click_add")

    page.locator('button:has-text("Watch advertisment")').click()
    shot(page, "07_after_watch_ad")

    print("⏳ 等待 2 分钟", flush=True)
    time.sleep(120)

# ================= 主程序 =================
def main():
    ensure_dir(SCREENSHOT_DIR)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,   # 🔴 关键
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        page = browser.new_page()
        page.set_default_timeout(60000)

        try:
            if os.name != "nt":
                signal.alarm(TASK_TIMEOUT_SECONDS)

            login(page)
            add_time(page)

            if os.name != "nt":
                signal.alarm(0)

        except Exception as e:
            print(f"❌ 失败: {e}", flush=True)
            shot(page, "99_error")
            zip_screenshots()
            browser.close()
            exit(1)

        finally:
            browser.close()

    zip_screenshots()
    print("🎉 任务完成", flush=True)

if __name__ == "__main__":
    main()
