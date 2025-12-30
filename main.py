def login_with_playwright(page):
    cookie = os.environ.get("PTERODACTYL_COOKIE")
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")

    # ---------- Cookie + OAuth 登录 ----------
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

        # Authorization
        auth_span = page.locator('span:has-text("Authorization")')
        if auth_span.count() > 0:
            print("检测到 Authorization，正在点击...")
            auth_span.locator("xpath=ancestor::button").click()

            print("等待 OAuth 授权完成...")
            for _ in range(18):  # 最多 90 秒
                time.sleep(5)
                if page.locator('span:has-text("Authorization")').count() == 0:
                    print("✅ OAuth 授权完成")
                    break
            else:
                raise PlaywrightTimeoutError("OAuth 授权超时")

        # ⭐ 关键修复点：OAuth 成功后直接认为登录成功
        print("✅ 已通过 Cookie + OAuth 登录")
        return True

    # ---------- 账号密码登录（只有 Cookie 不存在时才会走） ----------
    if not email or not password:
        print("❌ 无法登录：未提供邮箱或密码")
        return False

    print("使用邮箱密码登录...")
    page.goto(LOGIN_URL, wait_until="networkidle")

    # 防止元素不存在直接点击
    login_tab = page.locator('a:has-text("Through login/password")')
    if login_tab.count() > 0:
        login_tab.click()

    page.fill('input[name="username"]', email)
    page.fill('input[name="password"]', password)

    with page.expect_navigation(wait_until="networkidle"):
        page.click('button[type="submit"]')

    return True
