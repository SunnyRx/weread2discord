import argparse
import os
import requests
from requests.utils import cookiejar_from_dict
from http.cookies import SimpleCookie
import random
import json

WEREAD_URL = "https://weread.qq.com/"
WEREAD_NOTEBOOKS_URL = "https://i.weread.qq.com/user/notebooks"
WEREAD_BOOKMARKLIST_URL = "https://i.weread.qq.com/book/bookmarklist"
WEREAD_CHAPTER_INFO = "https://i.weread.qq.com/book/chapterInfos"
WEREAD_REVIEW_LIST_URL = "https://i.weread.qq.com/review/list"


def parse_cookie_string(cookie_string):
    cookie = SimpleCookie()
    cookie.load(cookie_string)
    cookies_dict = {}
    cookiejar = None
    for key, morsel in cookie.items():
        cookies_dict[key] = morsel.value
        cookiejar = cookiejar_from_dict(
            cookies_dict, cookiejar=None, overwrite=True
        )
    return cookiejar


def get_bookmark_list(bookId):
    """获取我的划线"""
    params = dict(bookId=bookId)
    r = session.get(WEREAD_BOOKMARKLIST_URL, params=params)
    if r.ok:
        updated = r.json().get("updated")
        updated = sorted(updated, key=lambda x: (
            x.get("chapterUid", 1), int(x.get("range").split("-")[0])))
        return r.json()["updated"]
    return None


def get_review_list(bookId):
    """获取笔记"""
    params = dict(bookId=bookId, listType=11, mine=1, syncKey=0)
    r = session.get(WEREAD_REVIEW_LIST_URL, params=params)
    reviews = r.json().get("reviews")
    summary = list(filter(lambda x: x.get("review").get("type") == 4, reviews))
    reviews = list(filter(lambda x: x.get("review").get("type") == 1, reviews))
    reviews = list(map(lambda x: x.get("review"), reviews))
    reviews = list(map(lambda x: {**x, "markText": x.pop("content")}, reviews))
    return summary, reviews


def get_table_of_contents():
    """获取目录"""
    return {
        "type": "table_of_contents",
        "table_of_contents": {
            "color": "default"
        }
    }


def get_heading(level, content):
    if level == 1:
        heading = "heading_1"
    elif level == 2:
        heading = "heading_2"
    else:
        heading = "heading_3"
    return {
        "type": heading,
        heading: {
            "rich_text": [{
                "type": "text",
                "text": {
                    "content": content,
                }
            }],
            "color": "default",
            "is_toggleable": False
        }
    }


def get_quote(content):
    return {
        "type": "quote",
        "quote": {
            "rich_text": [{
                "type": "text",
                "text": {
                    "content": content
                },
            }],
            "color": "default"
        }
    }


def get_callout(content, style, colorStyle, reviewId):
    # 根据不同的划线样式设置不同的emoji 直线type=0 背景颜色是1 波浪线是2
    emoji = "🌟"
    if style == 0:
        emoji = "💡"
    elif style == 1:
        emoji = "⭐"
    # 如果reviewId不是空说明是笔记
    if reviewId != None:
        emoji = "✍️"
    color = "default"
    # 根据划线颜色设置文字的颜色
    if colorStyle == 1:
        color = "red"
    elif colorStyle == 2:
        color = "purple"
    elif colorStyle == 3:
        color = "blue"
    elif colorStyle == 4:
        color = "green"
    elif colorStyle == 5:
        color = "yellow"
    return {
        "type": "callout",
        "callout": {
            "rich_text": [{
                "type": "text",
                "text": {
                    "content": content,
                }
            }],
            "icon": {
                "emoji": emoji
            },
            "color": color
        }
    }


def get_chapter_info(bookId):
    """获取章节信息"""
    body = {
        'bookIds': [bookId],
        'synckeys': [0],
        'teenmode': 0
    }
    r = session.post(WEREAD_CHAPTER_INFO, json=body)
    if r.ok and "data" in r.json() and len(r.json()["data"]) == 1 and "updated" in r.json()["data"][0]:
        update = r.json()["data"][0]["updated"]
        return {item["chapterUid"]: item for item in update}
    return None


def get_notebooklist():
    """获取笔记本列表"""
    r = session.get(WEREAD_NOTEBOOKS_URL)
    if r.ok:
        data = r.json()
        books = data.get("books")
        books.sort(key=lambda x: x["sort"])
        return books
    else:
        print(r.text)
    return None


def get_children(chapter, summary, bookmark_list):
    children = []
    grandchild = {}
    if chapter != None:
        # 添加目录
        children.append(get_table_of_contents())
        d = {}
        for data in bookmark_list:
            chapterUid = data.get("chapterUid", 1)
            if (chapterUid not in d):
                d[chapterUid] = []
            d[chapterUid].append(data)
        for key, value in d.items():
            if key in chapter:
                # 添加章节
                children.append(get_heading(
                    chapter.get(key).get("level"), chapter.get(key).get("title")))
            for i in value:
                markText = i.get("markText")
                for j in range(0, len(markText)//2000+1):
                    children.append(get_callout(markText[j*2000:(j+1)*2000],i.get("style"), i.get("colorStyle"), i.get("reviewId")))
                if i.get("abstract") != None and i.get("abstract") != "":
                    quote = get_quote(i.get("abstract"))
                    grandchild[len(children)-1] = quote

    else:
        # 如果没有章节信息
        for data in bookmark_list:
            markText = data.get("markText")
            for i in range(0, len(markText)//2000+1):
                children.append(get_callout(markText[i*200:(i+1)*2000],
                                data.get("style"), data.get("colorStyle"), data.get("reviewId")))
    if summary != None and len(summary) > 0:
        children.append(get_heading(1, "点评"))
        for i in summary:
            content = i.get("review").get("content")
            for j in range(0, len(content)//2000+1):
                children.append(get_callout(content[j*2000:(j+1)*2000], i.get(
                    "style"), i.get("colorStyle"), i.get("review").get("reviewId")))
    return children, grandchild


def get_webhook_url():
    file_dir = os.path.dirname(os.path.realpath('__file__'))
    
    config_file_path = os.path.join(file_dir, "config.json")
    webhook_url = ""

    with open(config_file_path, "r") as config_file:
        config = json.load(config_file)
        if "webhookUrl" in config:
            webhook_url = config["webhookUrl"]

    if webhook_url == "":
        print("无法读取 Discord Webhook URL。\n请检查配置文件。")
        exit()

    return webhook_url


def get_weread_cookie():
    file_dir = os.path.dirname(os.path.realpath('__file__'))
    
    config_file_path = os.path.join(file_dir, "config.json")
    weread_cookie = ""

    with open(config_file_path, "r") as config_file:
        config = json.load(config_file)
        if "wereadCookie" in config:
            weread_cookie = config["wereadCookie"]

    if weread_cookie == "":
        print("无法读取 Weread Cookie。\n请检查配置文件。")
        exit()

    return weread_cookie


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("weread_cookie")
    parser.add_argument("discord_webhook_url")
    options = parser.parse_args()
    if options.weread_cookie != None:
        weread_cookie = options.weread_cookie
    else:
        print("argparse 中没有传入 Weread Cookie")
        weread_cookie = get_weread_cookie()
    if options.discord_webhook_url != None:
        webhook_url = options.discord_webhook_url
    else:
        print("argparse 中没有传入 Discord Webhook URL")
        webhook_url = get_webhook_url()
    session = requests.Session()
    session.cookies = parse_cookie_string(weread_cookie)
    session.get(WEREAD_URL)
    books = get_notebooklist()

    i = 0
    memos = []
    if (books != None):
        for book in books:
            i +=1
            book = book.get("book")
            title = book.get("title")
            author = book.get("author")
            bookId = book.get("bookId")
            print(f"正在同步 {title} ,一共{len(books)}本，当前是第{i}本。")
            chapter = get_chapter_info(bookId)
            bookmark_list = get_bookmark_list(bookId)
            summary, reviews = get_review_list(bookId)
            bookmark_list.extend(reviews)
            bookmark_list = sorted(bookmark_list, key=lambda x: (
                x.get("chapterUid", 1), 0 if (x.get("range", "") == "" or x.get("range").split("-")[0]=="" ) else int(x.get("range").split("-")[0])))
            children, grandchild = get_children(
                chapter, summary, bookmark_list)

            for child in children:
                if child.get("type") == "callout":
                    callout = child.get("callout")
                    emoji = callout.get("icon", {}).get("emoji")
                    rich_text = callout.get("rich_text", [])
                    content = next((t.get("text", {}).get("content") for t in rich_text), None)
                    text = emoji + " " + content
                    quote_text = None
                    if grandchild.get(children.index(child)):
                        quote_text = grandchild.get(children.index(child)).get("quote").get("rich_text", [{}])[0].get("text", {}).get("content")
                    if text:
                        memos.append((title, quote_text, author, text))

        if (memos != []):
            count = 5

            message = f"早上好！\n 以下是今天为您挑选的 {count} 条读书笔记：\n\n"

            lottoyMemos = random.sample(memos, k=min(count, len(memos)))

            for memo in lottoyMemos:
                title, quote_text, author, text = memo
                message += f"{text}\n"
                if quote_text != None and quote_text != "":
                    message += f"> {quote_text}\n"
                message += f"—— 《{title}》（{author})\n\n"

            embed = {
                "title": "我的读书笔记随选",
                "description": message,
                "color": 2763306
            }

            embeds = [embed]

            content = {
                "content": "",
                "embeds": embeds
            }

            json_data = json.dumps(content)

            response = requests.post(webhook_url, json=content)

            try:
                response.raise_for_status()
            except response.exceptions.HTTPError as err:
                print(err)
            else:
                print("Payload delivered successfully, code {}.".format(response.status_code))

