import os
import time
import signal
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================= 配置 =================
SERVER_URL = "https://panel.godlike.host/server/61b8ad3c"
LOGIN_URL = "https://panel.godlike.host/auth/login"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"
TASK_TIMEOUT_SECONDS = 300  # 5 分钟

# ================= 超时控制 =================
class TaskTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行时间超过设定阈值")

if os.name != "nt":
    signal.signal(signal.SIGALRM, timeout_handler)

# ================= 登录逻辑（含 Authorization） =================
def login_with_playwright(page):
    cookie = os.environ.get("PTERODACTYL_COOKIE")
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")

    # ---------- Cookie 登录 ----------
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

        # ---------- Authorization（OAuth） ----------
        auth_span = page.locator('span:has-text("Authorization")')
        if auth_span.count() > 0:
            print("检测到 Authorization，正在点击...")
            auth_span.locator("xpath=ancestor::button").click()

            print("等待 OAuth 授权完成...")
            for _ in range(18):  # 最多 90 秒
                time.sleep(5)
                if "/server/" in page.url:
                    page.wait_for_timeout(3000)
                    print("✅ OAuth 授权完成")
                    return True

            raise PlaywrightTimeoutError("OAuth 授权超时")

        if "/server/" in page.url:
            print("✅ Cookie 登录成功")
            return True

        print("Cookie 登录失败，回退账号密码登录")
        page.context.clear_cookies()

    # ---------- 账号密码登录 ----------
    if not email or not password:
        print("❌ 无法登录：未提供邮箱或密码")
        return False

    print("使用邮箱密码登录...")
    page.goto(LOGIN_URL, wait_until="networkidle")
    page.locator('a:has-text("Through login/password")').click()

    page.fill('input[name="username"]', email)
    page.fill('input[name="password"]', password)

    with page.expect_navigation(wait_until="networkidle"):
        page.click('button[type="submit"]')

    return "/server/" in page.url

# ================= 增加时长任务 =================
def add_time_task(page):
    try:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始执行增加时长任务")

        page.goto(SERVER_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        # ---------- Add 90 minutes ----------
        print("查找 Add 90 minutes...")
        for _ in range(18):  # 最多 90 秒
            span = page.locator('span:has-text("Add 90 minutes")')
            if span.count() > 0:
                span.locator("xpath=ancestor::button").click()
                print("✅ 已点击 Add 90 minutes")
                break
            time.sleep(5)
        else:
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

            print("🎉 本轮任务完成" if success else "❌ 本轮任务失败")

        finally:
            browser.close()
            print("浏览器已关闭，程序结束")

# ================= 入口 =================
if __name__ == "__main__":
    main()
