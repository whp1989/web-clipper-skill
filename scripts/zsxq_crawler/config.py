#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球爬虫配置文件 (zsxq-cli 版本)
使用官方 zsxq-cli 进行认证和 API 调用，无需手动维护 Cookie。
"""

# ==========================================
# 认证配置
# ==========================================
# 本程序依赖 zsxq-cli 的 OAuth 认证。
# 请确保已运行: zsxq-cli auth login
# Token 会自动存储在系统 Keychain 中，无需手动配置。
#
# 直接配置Access Token（可选，用于绕过zsxq-cli）
ZSXQ_ACCESS_TOKEN = "6a16530e00ba3f4069476c6301460b1c"

# ==========================================
# zsxq-cli 路径配置
# ==========================================
# 如果 zsxq-cli 不在系统 PATH 中，请填写完整路径
# Windows 默认 npm 全局安装路径示例：
ZSXQ_CLI_PATH = r"C:\Users\Pandaponds_AI\AppData\Roaming\npm\node_modules\zsxq-cli\npm\bin\zsxq-cli.exe"

# ==========================================
# 请求配置
# ==========================================
# 每次请求间隔（秒），用于避免触发风控
# 官方 CLI 有内置限流，但增加延迟更安全
REQUEST_DELAY = 1.5

# 每页最大获取条数（zsxq-cli 限制最大 30）
MAX_TOPICS_PER_PAGE = 30

# 单次运行最大翻页数（防止意外死循环）
MAX_PAGES = 200

# ==========================================
# 目标配置
# ==========================================
# 目标星球ID（二月麦的星球，一般不需要修改）
GROUP_ID = "48888584885518"

# 输出目录（按剪藏skill规范，使用当前日期）
# 注意：虽然爬取的是前一天的帖子，但文件存放在当天的文件夹中
# 例如：5月6日凌晨爬取5月5日的帖子，存放在 2026-05-06 文件夹
OUTPUT_DIR = "/root/.openclaw/workspace/syncthing/raw/2026-05-06"

# 附件下载目录（与每日剪藏文件夹同级）
MULTIMEDIA_DIR = "/root/.openclaw/workspace/syncthing/raw/multimedia"

# 请求头User-Agent（一般不需要修改）
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ==========================================
# API配置
# ==========================================
BASE_URL = "https://api.zsxq.com/v2"
