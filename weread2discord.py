import argparse
import random
import time

import requests

GATEWAY_URL = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.4"

# Discord embed 的 description 上限是 4096 字符
MAX_MEMO_CHARS = 600
MAX_MESSAGE_CHARS = 3800


def call_gateway(api_key, api_name, **params):
    """调用微信读书 Agent API 网关"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"api_name": api_name, "skill_version": SKILL_VERSION, **params}
    for attempt in range(1, 4):
        try:
            r = requests.post(GATEWAY_URL, json=body, headers=headers, timeout=30)
            if r.ok:
                data = r.json()
                if data.get("errcode") == 0:
                    if data.get("upgrade_info"):
                        print(f"微信读书 API 提示：{data['upgrade_info']}")
                    return data
                error = f"errcode {data.get('errcode')}：{data.get('errmsg', '')}"
            elif r.status_code == 401:
                # 鉴权失败重试也不会成功，直接报配置错误
                raise RuntimeError(
                    f"微信读书 API 鉴权失败（{r.text[:200]}），请检查 API Key 是否正确。")
            else:
                error = f"HTTP {r.status_code}：{r.text[:200]}"
        except requests.RequestException as err:
            error = str(err)
        print(f"调用 {api_name} 失败（第 {attempt} 次）：{error}")
        if attempt < 3:
            time.sleep(5)
    raise RuntimeError(f"调用 {api_name} 连续 3 次失败，已放弃。")


def get_notebooklist(api_key):
    """获取笔记本列表，按 lastSort 游标翻页取全"""
    books = []
    last_sort = None
    while True:
        params = {"count": 20}
        if last_sort is not None:
            params["lastSort"] = last_sort
        data = call_gateway(api_key, "/user/notebooks", **params)
        page = data.get("books", [])
        books.extend(page)
        if data.get("hasMore") != 1 or not page:
            break
        last_sort = page[-1].get("sort")
        if last_sort is None:
            break
    books.sort(key=lambda x: x.get("sort", 0))
    return books


def get_bookmark_list(api_key, bookId):
    """获取我在一本书里的划线"""
    data = call_gateway(api_key, "/book/bookmarklist", bookId=bookId)
    return data.get("updated", [])


def get_review_list(api_key, bookId):
    """获取我在一本书里的笔记，按 synckey 翻页取全"""
    reviews = []
    synckey = 0
    while True:
        data = call_gateway(api_key, "/review/list/mine",
                            bookid=bookId, synckey=synckey, count=100)
        page = data.get("reviews", [])
        reviews.extend(page)
        next_synckey = data.get("synckey", synckey)
        if data.get("hasMore") != 1 or not page or next_synckey == synckey:
            break
        synckey = next_synckey
    return reviews


def highlight_emoji(item):
    # 直线 style=0，背景颜色是 1，波浪线是 2；带 reviewId 说明是笔记
    if item.get("reviewId") is not None:
        return "✍️"
    if item.get("style") == 0:
        return "💡"
    if item.get("style") == 1:
        return "⭐"
    return "🌟"


def collect_memos(api_key, books):
    """把所有书的划线和笔记摊平成（书名， 引用原文， 作者， 正文）元组"""
    memos = []
    for i, notebook in enumerate(books, start=1):
        book = notebook.get("book", {})
        title = book.get("title")
        author = book.get("author")
        bookId = book.get("bookId")
        print(f"正在同步 {title}，一共 {len(books)} 本，当前是第 {i} 本。")
        for item in get_bookmark_list(api_key, bookId):
            markText = item.get("markText")
            if not markText:
                continue
            memos.append(
                (title, None, author, f"{highlight_emoji(item)} {markText}"))
        for item in get_review_list(api_key, bookId):
            review = item.get("review", {})
            content = review.get("content")
            if not content:
                continue
            abstract = review.get("abstract")
            memos.append(
                (title, abstract or None, author, f"✍️ {content}"))
    return memos


def build_message(memos):
    count = 5
    picked = random.sample(memos, k=min(count, len(memos)))
    body = ""
    used = 0
    for title, quote_text, author, text in picked:
        memo = text if len(text) <= MAX_MEMO_CHARS else text[:MAX_MEMO_CHARS] + "…"
        if quote_text:
            quote = quote_text if len(quote_text) <= MAX_MEMO_CHARS else quote_text[:MAX_MEMO_CHARS] + "…"
            memo += f"\n> {quote}"
        memo += f"\n—— 《{title}》（{author}）\n\n"
        if len(body) + len(memo) > MAX_MESSAGE_CHARS:
            break
        body += memo
        used += 1
    return f"主人，早上好！\n 以下是今天为您挑选的 {used} 条读书笔记：\n\n{body}"


def send_to_discord(webhook_url, memos):
    message = build_message(memos)
    embed = {
        "title": "我的读书笔记随选",
        "description": message,
        "color": 2763306
    }
    response = requests.post(
        webhook_url, json={"content": "", "embeds": [embed]}, timeout=30)
    response.raise_for_status()
    print("Payload delivered successfully, code {}.".format(
        response.status_code))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("weread_api_key")
    parser.add_argument("discord_webhook_url")
    options = parser.parse_args()

    if not options.weread_api_key.startswith("wrk-"):
        print("警告：微信读书 API Key 通常以 wrk- 开头，请确认是否复制完整。")

    books = get_notebooklist(options.weread_api_key)
    memos = collect_memos(options.weread_api_key, books)
    if not memos:
        print("没有获取到任何划线或笔记。")
    else:
        send_to_discord(options.discord_webhook_url, memos)
