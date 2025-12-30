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
DOWNLOAD_DIR = "downloaded"
SCREENSHOT_ZIP = "screenshots.zip"
TASK_TIMEOUT_SECONDS = 300

# ================= GitHub 配置 =================
REPO = os.environ.get("GITHUB_REPOSITORY")  # owner/repo
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

# ================= GitHub Release =================
def github_post(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    return urllib.request.urlopen(req)

def create_release():
    with github_post(
        f"{GITHUB_API}/repos/{REPO}/releases",
        {
            "tag_name": TAG,
            "name": TAG,
            "draft": False,
            "prerelease": False,
        },
    ) as resp:
        data = json.loads(resp.read().decode())
        return data["upload_url"].split("{")[0]

def upload_asset(upload_url, filepath):
    name = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        data = f.read()
    req = urllib.request.Request(
        f"{upload_url}?name={name}",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/octet-stream",
        },
    )
    urllib.request.urlopen(req)
    return f"https://github.com/{REPO}/releases/download/{TAG}/{name}"

# ================= 禁止重定向 =================
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def download_via_github_signed(stable_url, out_path):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(
        stable_url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/octet-stream",
        },
    )
    try:
        opener.open(req)
        raise RuntimeError("未捕获到 GitHub 重定向")
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302):
            raise
        signed_url = e.headers.get("Location")
        print("🔐 GitHub 内部临时 URL：", flush=True)
        print(signed_url, flush=True)
        urllib.request.urlretrieve(signed_url, out_path)
        print(f"⬇️ 已通过临时凭证下载: {out_path}", flush=True)

# ================= Godlike 登录 =================
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

    auth_span = page.locator('span:has-text("Authorization")')
    if auth_span.count() > 0:
        take_screenshot(page, "02_before_authorization")
        auth_span.locator("xpath=ancestor::button").click()

        for _ in range(18):
            time.sleep(5)
            if page.locator('span:has-text("Authorization")').count() == 0:
                take_screenshot(page, "03_after_authorization")
                break
        else:
            raise PlaywrightTimeoutError("OAuth 授权超时")

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

            print("等待 2 分钟...", flush=True)
            time.sleep(120)

            return [before_img, after_img, final_img]

        time.sleep(5)

    # ⭐ 业务不可用分支（不是异常）
    print("ℹ️ 当前不可加时（未出现 Add 90 minutes），跳过本轮", flush=True)
    skip_img = take_screenshot(page, "07_add_90_not_available")
    return [before_img, skip_img]

# ================= 主程序 =================
def main():
    ensure_dir(SCREENSHOT_DIR)
    ensure_dir(DOWNLOAD_DIR)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
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

    print("🚀 创建 GitHub Release...", flush=True)
    upload_url = create_release()

    for img in screenshots:
        stable = upload_asset(upload_url, img)
        download_via_github_signed(
            stable,
            f"{DOWNLOAD_DIR}/{os.path.basename(img)}"
        )

    zip_screenshots()

if __name__ == "__main__":
    main()
