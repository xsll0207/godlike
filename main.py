import os
import time
import signal
import zipfile
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================= GitHub 配置 =================
REPO = os.environ.get("GITHUB_REPOSITORY")  # owner/repo
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_API = "https://api.github.com"

# ================= 业务配置 =================
SERVER_URL = "https://panel.godlike.host/server/61b8ad3c"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"

SCREENSHOT_DIR = "screenshots"
DOWNLOAD_DIR = "downloaded"
TAG = f"screenshots-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

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

def screenshot(page, name):
    path = f"{SCREENSHOT_DIR}/{name}.png"
    page.screenshot(path=path)
    print(f"📸 截图完成: {path}", flush=True)
    return path

# ================= GitHub Release =================
def create_release():
    url = f"{GITHUB_API}/repos/{REPO}/releases"
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "tag_name": TAG,
            "name": TAG,
            "draft": False,
            "prerelease": False,
        },
    )
    r.raise_for_status()
    return r.json()["upload_url"].split("{")[0]

def upload_asset(upload_url, filepath):
    name = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        r = requests.post(
            f"{upload_url}?name={name}",
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type": "application/octet-stream",
            },
            data=f,
        )
    r.raise_for_status()
    return f"https://github.com/{REPO}/releases/download/{TAG}/{name}"

# ================= 临时凭证下载 =================
def download_via_github_signed(url, out_path):
    r = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/octet-stream",
        },
        allow_redirects=False,
    )

    if r.status_code not in (301, 302):
        raise Exception("未获得 GitHub 重定向")

    signed_url = r.headers["Location"]
    print("🔐 GitHub 内部临时下载 URL：")
    print(signed_url)

    with requests.get(signed_url, stream=True) as resp:
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

    print(f"⬇️ 文件已通过临时凭证下载: {out_path}", flush=True)

# ================= 主程序 =================
def main():
    ensure_dir(SCREENSHOT_DIR)
    ensure_dir(DOWNLOAD_DIR)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.context.add_cookies([{
            "name": COOKIE_NAME,
            "value": os.environ["PTERODACTYL_COOKIE"],
            "domain": ".panel.godlike.host",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }])

        page.goto(SERVER_URL)
        img = screenshot(page, "01_open_server")
        browser.close()

    print("🚀 创建 GitHub Release...")
    upload_url = create_release()

    print("📤 上传截图...")
    stable_url = upload_asset(upload_url, img)

    print("⬇️ 使用 GitHub 内部临时凭证下载...")
    download_via_github_signed(
        stable_url,
        f"{DOWNLOAD_DIR}/01_open_server.png"
    )

if __name__ == "__main__":
    main()
