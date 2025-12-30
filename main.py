import os
import time
import signal
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

# --- 配置项 ---
SERVER_URL = "https://panel.godlike.host/server/61b8ad3c"
LOGIN_URL = "https://panel.godlike.host/auth/login"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"
TASK_TIMEOUT_SECONDS = 300  # 5分钟

# --- 超时处理机制 ---
class TaskTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行时间超过设定的阈值")

if os.name != 'nt':
    signal.signal(signal.SIGALRM, timeout_handler)

# ================= 登录逻辑（已修复 Authorization） =================
def login_with_playwright(page):
    remember_web_cookie = os.environ.get("PTERODACTYL_COOKIE")
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")

    # ---------- Cookie 登录 ----------
    if remember_web_cookie:
        print("检测到 PTERODACTYL_COOKIE，尝试使用 Cookie 登录...")
        page.context.add_cookies([{
            "name": COOKIE_NAME,
            "value": remember_web_cookie,
            "domain": ".panel.godlike.host",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }])

        page.goto(SERVER_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # 🔑 关键：Authorization 页面
        auth_span = page.locator('span:has-text("Authorization")')
if auth_span.count() > 0:
    print("检测到 Authorization，正在点击...")
    auth_span.locator("xpath=ancestor::button").click()

    print("等待 OAuth 授权完成并返回服务器页面...")
    for _ in range(18):  # 最多 90 秒
        time.sleep(5)
        if "/server/" in page.url:
            page.wait_for_timeout(3000)
            print("✅ OAuth 授权完成")
            break
    else:
        raise PlaywrightTimeoutError("OAuth 授权超时，未返回服务器页面")


# 最多等待 90 秒，轮询 URL
success = False
for _ in range(18):  # 18 × 5s = 90s
    time.sleep(5)
    print("当前 URL:", page.url)
    if "/server/" in page.url:
        success = True
        break

if not success:
    raise PlaywrightTimeoutError("OAuth 授权后未返回 server 页面")

page.wait_for_timeout(3000)


        if "/server/" in page.url:
            print("✅ Cookie + Authorization 登录成功")
            return True

        print("Cookie 登录失败，回退到账号密码登录")
        page.context.clear_cookies()

    # ---------- 账号密码登录 ----------
    if not email or not password:
        print("❌ 无法登录：未提供邮箱或密码")
        return False

    page.goto(LOGIN_URL, wait_until="networkidle")
    page.locator('a:has-text("Through login/password")').click()

    page.fill('input[name="username"]', email)
    page.fill('input[name="password"]', password)

    with page.expect_navigation(wait_until="networkidle"):
        page.click('button[type="submit"]')

    return "/server/" in page.url

# ================= 增加时长任务（已修复选择器） =================
def add_time_task(page):
    try:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始增加时长")

        page.goto(SERVER_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        # ---------- Add 90 minutes ----------
        print("查找 Add 90 minutes...")
        found = False
        for _ in range(18):  # 最多 90 秒
            span = page.locator('span:has-text("Add 90 minutes")')
            if span.count() > 0:
                span.locator("xpath=ancestor::button").click()
                print("✅ 已点击 Add 90 minutes")
                found = True
                break
            time.sleep(5)

        if not found:
            raise PlaywrightTimeoutError("Add 90 minutes 未出现")

        # ---------- Watch advertisment ----------
        print("查找 Watch advertisment...")
        page.locator('button:has-text("Watch advertisment")') \
            .wait_for(state="visible", timeout=30000)
        page.locator('button:has-text("Watch advertisment")').click()
        print("✅ 已点击 Watch advertisment")

        # ---------- 固定等待 ----------
        print("等待 2 分钟...")
        time.sleep(120)

        return True

    except Exception as e:
        print(f"❌ 增加时长失败: {e}")
        page.screenshot(path="task_error.png")
        return False

# ================= 主程序 =================
def main():
    print("启动自动化任务...")
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

            print("🎉 任务完成" if success else "❌ 任务失败")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
