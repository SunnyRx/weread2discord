# 从微信读书中抽划线或笔记发送到 Discord

每天从微信读书中抽出 5 条划线或笔记，通过 Webhook 发送到 Discord 中。

[![built with Codeium](https://codeium.com/badges/main)](https://codeium.com)

## 感谢

灵感出自 **Readwise** 的**每日邮件回顾**。

代码改自 [https://github.com/malinkang/weread2notion](https://github.com/malinkang/weread2notion)

## 使用

1. Fork 这个工程
2. 获取微信读书的 Cookie
    * 浏览器打开 https://weread.qq.com/
    * 微信扫码登录确认，提示没有权限忽略即可
    * 按F12进入开发者模式，依次点「Network」->「Doc」->「Headers」->「cookie」，复制 Cookie 字符串
3. 获取 Discord 的 Webhook URL
    * 打开要发送消息的 Discord 服务器或频道（需要管理员或拥有者权限）
    * 打开服务器设置或频道设置
    * 在服务器或频道设置页面中，依次点「整合」->「Webhook」->「新 Webhook」->「新创建出来的 Webhook」->「复制 Webhook URL」
4. 在 GitHub 的 Secrets 中添加变量
    * 打开第一步 Fork 的工程，点击「Settings」->「Secrets and variables」->「New repository secret」
    * 添加以下变量
        * WEREAD_COOKIE
        * DISCORD_WEBHOOK_URL
