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
TASK_TIMEOUT_SECONDS = 300  # 5 分钟
SCREENSHOT_DIR = "screenshots"
SCREENSHOT_ZIP = "screenshots.zip"

# ================= 超时控制 =================
class TaskTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行时间超过设定阈值")

if os.name != "nt":
    signal.signal(signal.SIGALRM, timeout_handler)

# ================= 工具：阶段截图 =================
def ensure_screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def take_screenshot(page, stage):
    ensure_screenshot_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{stage}_{ts}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)
    page.screenshot(path=path)
    print(f"📸 已保存截图: {path}")

def zip_screenshots():
    if not os.path.isdir(SCREENSHOT_DIR):
        return
    with zipfile.ZipFile(SCREENSHOT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(SCREENSHOT_DIR):
            for f in files:
                full_path = os.path.join(root, f)
                zf.write(full_path, arcname=f)
    print(f"📦 已打包截图为 {SCREENSHOT_ZIP}")

# ================= 登录逻辑（Cookie + OAuth） =================
def login_with_playwright(page):
    cookie = os.environ.get("PTERODACTYL_COOKIE")
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")

    if cookie:
        print("检测到 PTERODACTYL_COOKIE，尝试使用 Cookie 登录...")
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

        auth_span = page.locator('span:has-text("Authorization")')
        if auth_span.count() > 0:
            take_screenshot(page, "02_before_authorization")
            print("检测到 Authorization，正在点击...")
            auth_span.locator("xpath=ancestor::button").click()

            print("等待 OAuth 授权完成...")
            for _ in range(18):
                time.sleep(5)
                if page.locator('span:has-text("Authorization")').count() == 0:
                    take_screenshot(page, "03_after_authorization")
                    print("✅ OAuth 授权完成")
                    break
            else:
                raise PlaywrightTimeoutError("OAuth 授权超时")

        print("✅ 已通过 Cookie + OAuth 登录")
        return True

    # 兜底：账号密码登录
    if not email or not password:
        print("❌ 无法登录：未提供邮箱或密码")
        return False

    print("使用邮箱密码登录...")
    page.goto(LOGIN_URL, wait_until="networkidle")
    login_tab = page.locator('a:has-text("Through login/password")')
    if login_tab.count() > 0:
        login_tab.click()

    page.fill('input[name="username"]', email)
    page.fill('input[name="password"]', password)

    with page.expect_navigation(wait_until="networkidle"):
        page.click('button[type="submit"]')

    return True

# ================= 增加时长任务 =================
def add_time_task(page):
    try:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始执行增加时长任务")

        page.goto(SERVER_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)
        take_screenshot(page, "04_before_add_90_minutes")

        print("查找 Add 90 minutes...")
        for _ in range(18):
            span = page.locator('span:has-text("Add 90 minutes")')
            if span.count() > 0:
                span.locator("xpath=ancestor::button").click()
                take_screenshot(page, "05_after_click_add_90_minutes")
                print("✅ 已点击 Add 90 minutes")
                break
            time.sleep(5)
        else:
            raise PlaywrightTimeoutError("Add 90 minutes 未出现")

        print("查找 Watch advertisment...")
        page.locator('button:has-text("Watch advertisment")') \
            .wait_for(state="visible", timeout=30000)
        page.locator('button:has-text("Watch advertisment")').click()
        take_screenshot(page, "06_after_click_watch_ad")

        print("等待 2 分钟...")
        time.sleep(120)

        return True

    except Exception as e:
        print(f"❌ 增加时长失败: {e}")
        take_screenshot(page, "99_error")
        return False

# ================= 主程序 =================
def main():
    print("启动自动化任务...")
    ensure_screenshot_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)

        try:
            if not login_with_playwright(page):
                print("❌ 登录失败")
                return

            if os.name != "nt":
                signal.alarm(TASK_TIMEOUT_SECONDS)

            success = add_time_task(page)

            if os.name != "nt":
                signal.alarm(0)

            print("🎉 本轮任务完成" if success else "❌ 本轮任务失败")

        finally:
            browser.close()
            zip_screenshots()
            print("浏览器已关闭，程序结束")

# ================= 入口 =================
if __name__ == "__main__":
    main()
