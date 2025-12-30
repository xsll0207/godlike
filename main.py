import os
import time
import signal
import zipfile
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================= 基础配置 =================
SERVER_URL = "https://panel.godlike.host/server/61b8ad3c"
LOGIN_URL = "https://panel.godlike.host/auth/login"
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

# ================= 登录逻辑（终态最稳） =================
def login_with_playwright(page):
    """
    登录顺序：
    1. Cookie + OAuth
    2. 如果未真正进入 /server → 账号密码（需点击 Through login/password）
    """

    # ---------- Step 1: Cookie + OAuth ----------
    cookie = os.environ.get("PTERODACTYL_COOKIE")
    if cookie:
        print("🔐 尝试 Cookie + OAuth 登录...", flush=True)
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

        auth_btn = page.locator('span:has-text("Authorization")')
        if auth_btn.count() > 0:
            take_screenshot(page, "02_before_authorization")
            print("➡️ 点击 Authorization...", flush=True)
            auth_btn.locator("xpath=ancestor::button").click()

            for _ in range(18):
                time.sleep(5)
                if "/server/" in page.url:
                    take_screenshot(page, "03_after_authorization")
                    print("✅ OAuth 成功", flush=True)
                    return

        print("⚠️ OAuth 未成功，回退账号密码登录", flush=True)

    # ---------- Step 2: 账号密码登录 ----------
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")
    if not email or not password:
        raise Exception("❌ OAuth 失败，且未提供账号密码")

    print("🔑 使用账号密码登录...", flush=True)
    page.goto(LOGIN_URL, wait_until="networkidle")
    take_screenshot(page, "LOGIN_PAGE")

    # ⭐ 关键修复点：切换到 login/password
    login_tab = page.locator('text=Through login/password')
    if login_tab.count() > 0:
        print("➡️ 切换到账号密码登录方式", flush=True)
        login_tab.click()
        page.wait_for_timeout(500)

    # 等输入框真正可见
    page.wait_for_selector('input[name="username"]', state="visible", timeout=30000)
    page.wait_for_selector('input[name="password"]', state="visible", timeout=30000)

    page.fill('input[name="username"]', email)
    page.fill('input[name="password"]', password)

    page.click('button[type="submit"]')

    # 强制进入服务器页面
    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(3000)

    if "/server/" not in page.url:
        take_screenshot(page, "LOGIN_FAILED")
        raise Exception("❌ 账号密码登录失败")

    take_screenshot(page, "LOGIN_SUCCESS")
    print("✅ 账号密码登录成功", flush=True)

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

    # 业务不可用（不是异常）
    print("ℹ️ 当前不可加时，跳过本轮", flush=True)
    skip_img = take_screenshot(page, "07_add_90_not_available")
    return [before_img, skip_img]

# ================= 主程序 =================
def main():
    print("🚀 启动 Godlike 自动加时任务", flush=True)
    ensure_dir(SCREENSHOT_DIR)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        page.set_default_timeout(60000)

        try:
            if os.name != "nt":
                signal.alarm(TASK_TIMEOUT_SECONDS)

            login_with_playwright(page)
            add_time_task(page)

            if os.name != "nt":
                signal.alarm(0)

        except Exception as e:
            print(f"❌ 任务失败: {e}", flush=True)
            take_screenshot(page, "99_error")
            zip_screenshots()
            browser.close()
            exit(1)

        finally:
            browser.close()

    zip_screenshots()
    print("🎉 本轮任务结束", flush=True)

if __name__ == "__main__":
    main()
