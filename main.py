import os
import time
import signal
import zipfile
from datetime import datetime
from playwright.sync_api import sync_playwright

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

# ================= 登录逻辑（强制 Through login/password） =================
def login_with_password(page):
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")
    if not email or not password:
        raise Exception("未提供账号密码")

    # 如果有 cookie，先注入（能省一次登录）
    cookie = os.environ.get("PTERODACTYL_COOKIE")
    if cookie:
        page.context.add_cookies([{
            "name": COOKIE_NAME,
            "value": cookie,
            "domain": ".panel.godlike.host",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }])

    # 访问服务器页面
    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)
    shot(page, "01_open_server")

    # 如果已经进 server，直接成功
    if "/server/" in page.url:
        print("✅ Cookie 已登录", flush=True)
        return

    # 确认在 Login to continue 页面
    page.wait_for_timeout(2000)

    # ⭐ 核心：点击 Through login/password
    switch = page.locator('text=Through login/password')
    if switch.count() == 0 or not switch.first.is_visible():
        shot(page, "NO_THROUGH_LOGIN_PASSWORD")
        raise Exception("未找到 Through login/password 按钮")

    print("➡️ 点击 Through login/password", flush=True)
    switch.first.click(force=True)
    time.sleep(500)

    shot(page, "02_after_click_through_login")

    # 等账号密码表单真正可见
    page.wait_for_selector('input[name="username"], input[name="email"]', state="visible", timeout=30000)
    page.wait_for_selector('input[type="password"]', state="visible", timeout=30000)

    # 取可见的输入框
    user_inputs = page.locator('input[name="username"], input[name="email"]')
    pass_inputs = page.locator('input[type="password"]')

    user_box = None
    pass_box = None

    for i in range(user_inputs.count()):
        if user_inputs.nth(i).is_visible():
            user_box = user_inputs.nth(i)
            break

    for i in range(pass_inputs.count()):
        if pass_inputs.nth(i).is_visible():
            pass_box = pass_inputs.nth(i)
            break

    if not user_box or not pass_box:
        shot(page, "LOGIN_FORM_NOT_VISIBLE")
        raise Exception("账号密码输入框不可见")

    user_box.scroll_into_view_if_needed()
    pass_box.scroll_into_view_if_needed()

    user_box.fill(email)
    pass_box.fill(password)

    shot(page, "03_before_login_submit")

    # 点击 Login
    login_buttons = page.locator('button:has-text("Login")')
    clicked = False
    for i in range(login_buttons.count()):
        btn = login_buttons.nth(i)
        if btn.is_visible():
            btn.click(force=True)
            clicked = True
            break

    if not clicked:
        shot(page, "LOGIN_BUTTON_NOT_VISIBLE")
        raise Exception("Login 按钮不可见")

    time.sleep(3)
    shot(page, "04_after_login_submit")

    # 强制进入 server 页面
    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)

    if "/server/" not in page.url:
        shot(page, "LOGIN_FAILED")
        raise Exception("账号密码登录失败")

    shot(page, "05_login_success")
    print("✅ 账号密码登录成功", flush=True)

# ================= 加时逻辑 =================
def add_time_task(page):
    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(5000)
    shot(page, "06_before_add_90_minutes")

    btn = page.locator('span:has-text("Add 90 minutes")')
    if btn.count() == 0:
        print("ℹ️ 当前不可加时", flush=True)
        shot(page, "07_add_not_available")
        return

    btn.locator("xpath=ancestor::button").click()
    shot(page, "08_after_click_add")

    page.locator('button:has-text("Watch advertisment")').click()
    shot(page, "09_after_watch_ad")

    print("⏳ 等待 2 分钟", flush=True)
    time.sleep(120)

# ================= 主程序 =================
def main():
    print("🚀 启动 Godlike 自动加时任务（Through login/password）", flush=True)
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

            login_with_password(page)
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
