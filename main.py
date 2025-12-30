import os
import time
import signal
import json
import urllib.request
import urllib.error
from datetime import datetime
from playwright.sync_api import sync_playwright

# ================= GitHub 配置 =================
REPO = os.environ.get("GITHUB_REPOSITORY")  # owner/repo
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_API = "https://api.github.com"

if not GITHUB_TOKEN:
    raise RuntimeError("❌ 未检测到 GITHUB_TOKEN，请在 workflow 中注入 secrets.GITHUB_TOKEN")

# ================= 业务配置 =================
SERVER_URL = "https://panel.godlike.host/server/61b8ad3c"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"

SCREENSHOT_DIR = "screenshots"
DOWNLOAD_DIR = "downloaded"
TAG = f"screenshots-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# ================= 工具 =================
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def screenshot(page, name):
    path = f"{SCREENSHOT_DIR}/{name}.png"
    page.screenshot(path=path)
    print(f"📸 截图完成: {path}", flush=True)
    return path

# ================= GitHub API（urllib） =================
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
    url = f"{GITHUB_API}/repos/{REPO}/releases"
    with github_post(url, {
        "tag_name": TAG,
        "name": TAG,
        "draft": False,
        "prerelease": False,
    }) as resp:
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

# ================= 抓 GitHub 临时下载 URL =================
def download_via_github_signed(stable_url, out_path):
    req = urllib.request.Request(
        stable_url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/octet-stream",
        },
    )

    try:
        urllib.request.urlopen(req)
        raise RuntimeError("未触发 GitHub 重定向，无法获取临时 URL")
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302):
            raise

        signed_url = e.headers.get("Location")
        print("🔐 GitHub 内部临时下载 URL：", flush=True)
        print(signed_url, flush=True)

        urllib.request.urlretrieve(signed_url, out_path)
        print(f"⬇️ 已通过临时凭证下载: {out_path}", flush=True)

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

    print("🚀 创建 GitHub Release...", flush=True)
    upload_url = create_release()

    print("📤 上传截图...", flush=True)
    stable_url = upload_asset(upload_url, img)

    print("⬇️ 使用 GitHub 内部临时凭证下载...", flush=True)
    download_via_github_signed(
        stable_url,
        f"{DOWNLOAD_DIR}/01_open_server.png"
    )

if __name__ == "__main__":
    main()
