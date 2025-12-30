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

# ================= 截图工具 =================
def ensure_screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def take_screenshot(page, stage):
    ensure_screenshot_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCREENSHOT_DIR, f"{stage}_{ts}.png")
    page.screenshot(path=path)
    print(f"📸 已保存截图: {path}")

def zip_screenshots():
    if not os.path.isdir(SCREENSHOT_DIR):
        print("⚠️ screenshots 目录不存在，跳过打包")
        return

    files = os.listdir(SCREENSHOT_DIR)
    if not files:
        print("⚠️ screenshots 目录为空，跳过打包")
        return

    with zipfile.ZipFile(SCREENSHOT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(os.path.join(SCREENSHOT_DIR, f), arcname=f)

    print(f"📦 已生成 {SCREENSHOT_ZIP}")

# ================= 登录逻辑 =================
def login_with_playwright(page):
    cookie = os.environ.get("PTERODACTYL_COOKIE")

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
            auth_span.locator("xpath=ancestor::button").click()

            for _ in range(18):
                time.sleep(5)
                if page.locator('span:has-text("Authorization")').count() == 0:
                    take_screenshot(page, "03_after_authorization")
                    print("✅ OAuth 授权完成")
                    return True

        return True  # ⚠️ 不在这里 return False

    return False

# ================= 增加时长任务 =================
def add_time_task(page):
    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(5000)
    take_screenshot(page, "04_before_add_90_minutes")

    for _ in range(18):
        span = page.locator('span:has-text("Add 90 minutes")')
        if span.count() > 0:
            span.locator("xpath=ancestor::button").click()
            take_screenshot(page, "05_after_click_add_90_minutes")
            break
        time.sleep(5)
    else:
        raise PlaywrightTimeoutError("Add 90 minutes 未出现")

    page.locator('button:has-text("Watch advertisment")') \
        .wait_for(state="visible", timeout=30000)
    page.locator('button:has-text("Watch advertisment")').click()
    take_screenshot(page, "06_after_click_watch_ad")

    time.sleep(120)

# ================= 主程序 =================
def main():
    print("启动自动化任务...")
    ensure_screenshot_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)

        try:
            login_with_playwright(page)

            if os.name != "nt":
                signal.alarm(TASK_TIMEOUT_SECONDS)

            add_time_task(page)

            if os.name != "nt":
                signal.alarm(0)

            print("🎉 任务流程执行完成")

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            take_screenshot(page, "99_error")

        finally:
            browser.close()
            zip_screenshots()
            print("浏览器已关闭，程序结束")

# ================= 入口 =================
if __name__ == "__main__":
    main()
