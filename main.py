import os
import time
import signal
import zipfile
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================= 配置 =================
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

# ================= 登录逻辑 =================
def login_with_playwright(page):
    """
    顺序：
    1. Cookie + OAuth
    2. OAuth 失败 → Clientarea 账号密码（继续尝试）
    """

    cookie = os.environ.get("PTERODACTYL_COOKIE")
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")

    if not cookie:
        raise Exception("未提供 PTERODACTYL_COOKIE")

    # ---------- Cookie + OAuth ----------
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
    shot(page, "01_after_open_server")

    auth = page.locator('span:has-text("Authorization")')
    if auth.count() > 0:
        shot(page, "02_before_authorization")
        auth.locator("xpath=ancestor::button").click()
        print("➡️ 点击 Authorization", flush=True)

        for _ in range(10):
            time.sleep(2)
            if "/server/" in page.url:
                shot(page, "03_after_authorization")
                print("✅ OAuth 成功", flush=True)
                return

    print("⚠️ OAuth 未成功，进入 Clientarea 账号密码流程", flush=True)

    # ---------- Clientarea 登录 ----------
    if not email or not password:
        raise Exception("未提供账号密码，无法继续")

    page.goto(LOGIN_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)
    shot(page, "LOGIN_PAGE")

    # 切换到 Through login/password（如果存在）
    switch = page.locator('text=Through login/password')
    if switch.count() > 0:
        switch.click()
        time.sleep(500)

    # 多次尝试填写 & 提交
    for attempt in range(1, 4):
        print(f"🔁 Clientarea 登录尝试 {attempt}/3", flush=True)

        try:
            # 等字段真正可见
            page.wait_for_selector('input[name="email"]', state="visible", timeout=15000)
            page.wait_for_selector('input[name="password"]', state="visible", timeout=15000)

            # 滚动到表单
            page.locator('input[name="email"]').scroll_into_view_if_needed()

            page.fill('input[name="email"]', email)
            page.fill('input[name="password"]', password)

            # 强制点击 Login
            page.locator('button:has-text("Login")').click(force=True)

            time.sleep(3)
            shot(page, f"LOGIN_SUBMIT_{attempt}")

            # 强制返回服务器页面
            page.goto(SERVER_URL, wait_until="networkidle")
            time.sleep(2)

            if "/server/" in page.url:
                shot(page, "LOGIN_SUCCESS")
                print("✅ Clientarea 登录成功", flush=True)
                return

        except Exception as e:
            print(f"⚠️ 第 {attempt} 次登录异常: {e}", flush=True)

        time.sleep(3)

    # 走到这里说明失败
    shot(page, "LOGIN_FAILED")
    raise Exception("Clientarea 账号密码登录失败（多次尝试后）")

# ================= 加时逻辑 =================
def add_time_task(page):
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
    print Counting on your patience, let's push this further.
    ensure_dir(SCREENSHOT_DIR)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
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

            login_with_playwright(page)
            add_time_task(page)

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
    print("🎉 本轮任务结束", flush=True)

if __name__ == "__main__":
    main()
