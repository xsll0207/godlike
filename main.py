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
    """任务级强制超时异常"""
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行时间超过设定阈值")

if os.name != "nt":
    signal.signal(signal.SIGALRM, timeout_handler)

# ================= 基础工具 =================
def ensure_screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

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
    cookie = os.environ.get("PTERODACTYL_COOKIE")
    if not cookie:
        raise Exception("未提供 PTERODACTYL_COOKIE")

    print("检测到 PTERODACTYL_COOKIE，尝试使用 Cookie 登录...", flush=True)

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
    page.screenshot(path=f"{SCREENSHOT_DIR}/01_after_open_server.png")

    auth_span = page.locator('span:has-text("Authorization")')
    if auth_span.count() > 0:
        page.screenshot(path=f"{SCREENSHOT_DIR}/02_before_authorization.png")
        print("检测到 Authorization，正在点击...", flush=True)

        auth_span.locator("xpath=ancestor::button").click()

        print("等待 OAuth 授权完成...", flush=True)
        for _ in range(18):
            time.sleep(5)
            if page.locator('span:has-text("Authorization")').count() == 0:
                page.screenshot(path=f"{SCREENSHOT_DIR}/03_after_authorization.png")
                print("✅ OAuth 授权完成", flush=True)
                break
        else:
            raise PlaywrightTimeoutError("OAuth 授权超时")

    print("✅ Cookie + OAuth 登录完成", flush=True)

# ================= 增加时长任务 =================
def add_time_task(page):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始执行增加时长任务", flush=True)

    page.goto(SERVER_URL, wait_until="networkidle")
    page.wait_for_timeout(5000)
    page.screenshot(path=f"{SCREENSHOT_DIR}/04_before_add_90_minutes.png")

    print("查找 Add 90 minutes...", flush=True)
    for _ in range(18):
        span = page.locator('span:has-text("Add 90 minutes")')
        if span.count() > 0:
            span.locator("xpath=ancestor::button").click()
            page.screenshot(path=f"{SCREENSHOT_DIR}/05_after_click_add_90_minutes.png")
            print("✅ 已点击 Add 90 minutes", flush=True)
            break
        time.sleep(5)
    else:
        raise PlaywrightTimeoutError("Add 90 minutes 未出现")

    page.locator('button:has-text("Watch advertisment")') \
        .wait_for(state="visible", timeout=30000)
    page.locator('button:has-text("Watch advertisment")').click()
    page.screenshot(path=f"{SCREENSHOT_DIR}/06_after_click_watch_ad.png")

    print("等待 2 分钟...", flush=True)
    time.sleep(120)

# ================= 主程序 =================
def main():
    print("启动自动化任务...", flush=True)
    ensure_screenshot_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)

        try:
            if os.name != "nt":
                signal.alarm(TASK_TIMEOUT_SECONDS)

            login_with_playwright(page)
            add_time_task(page)

            if os.name != "nt":
                signal.alarm(0)

            print("🎉 本轮任务成功完成", flush=True)

        except TaskTimeoutError as e:
            print(f"🔥🔥🔥 任务强制超时（{TASK_TIMEOUT_SECONDS}秒）！🔥🔥🔥", flush=True)
            print(f"错误信息: {e}", flush=True)
            page.screenshot(path="task_force_timeout_error.png")
            zip_screenshots()
            browser.close()
            exit(1)

        except Exception as e:
            print(f"主程序发生严重错误: {e}", flush=True)
            page.screenshot(path="main_critical_error.png")
            zip_screenshots()
            browser.close()
            exit(1)

        finally:
            zip_screenshots()
            browser.close()
            print("浏览器已关闭，程序结束", flush=True)

# ================= 入口 =================
if __name__ == "__main__":
    main()
