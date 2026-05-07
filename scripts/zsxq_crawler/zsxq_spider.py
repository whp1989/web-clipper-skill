#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球爬虫 - zsxq-cli 版本
通过官方 CLI 调用 API，无需手动维护 Cookie。
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import time
import json
import os
import re
from datetime import datetime
from pathlib import Path

from config import GROUP_ID, OUTPUT_DIR, MAX_TOPICS_PER_PAGE, MAX_PAGES
from zsxq_cli_client import ZsxqCliClient, ZsxqCliError


class ZsxqSpider:
    """知识星球爬虫类 (zsxq-cli 版本)"""

    def __init__(self, cli_path=None, obsidian_path=None):
        """
        初始化爬虫

        Args:
            cli_path: zsxq-cli 路径，None 则使用 config 中的配置
            obsidian_path: Obsidian 仓库路径
        """
        self.client = ZsxqCliClient(cli_path=cli_path)
        self.obsidian_path = obsidian_path or self._find_obsidian_path()
        self.group_id = GROUP_ID

        # 确保 Obsidian 文件夹存在
        self._ensure_obsidian_folder()

    def _find_obsidian_path(self):
        """自动查找 Obsidian 仓库路径"""
        possible_paths = [
            os.path.expanduser("~/Documents/Obsidian"),
            os.path.expanduser("~/Documents/Obsidian Vault"),
            os.path.expanduser("~/Obsidian"),
            "/d/Investing/Investing/Obsidian",
            "/d/Investing/Investing/Obsidian Vault",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                print(f"[INFO] 找到 Obsidian 路径: {path}")
                return path
        default_path = os.path.expanduser("~/Documents/Obsidian/ZSXQ")
        print(f"[WARN] 未找到 Obsidian 路径，使用默认路径: {default_path}")
        return default_path

    def _ensure_obsidian_folder(self):
        """确保 Obsidian 中的输出文件夹存在"""
        self.zsxq_folder = OUTPUT_DIR
        os.makedirs(self.zsxq_folder, exist_ok=True)
        print(f"[INFO] 输出文件夹: {self.zsxq_folder}")

        self.time_record_path = os.path.join(os.path.dirname(__file__), "time.md")
        os.makedirs(os.path.dirname(self.time_record_path) or ".", exist_ok=True)

    def get_last_crawl_time(self):
        """读取上次爬取的时间戳"""
        default_time = "2026-04-11T23:59:00+08:00"
        if not os.path.exists(self.time_record_path):
            print(f"[INFO] 未找到时间记录文件，使用首次默认时间: {default_time}")
            return default_time
        try:
            with open(self.time_record_path, 'r', encoding='utf-8') as f:
                content = f.read()
            for line in content.split('\n'):
                if '上次爬取截止时间' in line and ':' in line:
                    time_str = line.split(':', 1)[1].strip()
                    time_str = time_str.replace('**', '').strip()
                    print(f"[INFO] 上次爬取截止时间: {time_str}")
                    return time_str
            print(f"[WARN] 时间记录文件格式异常，使用默认时间: {default_time}")
            return default_time
        except Exception as e:
            print(f"[ERROR] 读取时间记录文件失败: {e}，使用默认时间: {default_time}")
            return default_time

    def save_last_crawl_time(self, last_topic_time):
        """保存最后爬取的文章时间戳"""
        try:
            dt = datetime.fromisoformat(last_topic_time.replace("Z", "+00:00"))
            unix_ms = int(dt.timestamp() * 1000)
            content = f"""# 知识星球爬虫时间戳记录

## 说明
此文件用于记录上次爬虫最后一篇文章的发布时间，以便下次增量爬取。

## 时间戳
**上次爬取截止时间**: {last_topic_time}

**Unix 时间戳 (毫秒)**: {unix_ms}

---
*此文件由爬虫自动更新，请勿手动修改*
"""
            with open(self.time_record_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[INFO] 已更新爬取时间戳: {last_topic_time}")
            return True
        except Exception as e:
            print(f"[ERROR] 保存时间戳失败: {e}")
            return False

    def check_auth(self):
        """检查认证状态"""
        print("[INFO] 检查 zsxq-cli 认证状态...")
        user_info = self.client.get_user_info()
        if user_info and user_info.get("name"):
            print(f"[SUCCESS] 认证有效: {user_info.get('name')}")
            return True
        print("[ERROR] 认证无效，请运行: zsxq-cli auth login")
        return False

    def get_group_info(self):
        """获取星球信息"""
        return self.client.get_group_info(self.group_id)

    def get_topics(self, count=10, end_time=None):
        """
        获取主题列表（自动分页）

        Args:
            count: 期望获取的总数量（实际可能因分页限制分多次请求）
            end_time: 分页时间戳

        Returns:
            list: 主题列表
        """
        all_topics = []
        current_end_time = end_time
        remaining = count

        while remaining > 0 and len(all_topics) < count:
            limit = min(remaining, MAX_TOPICS_PER_PAGE)
            result = self.client.get_topics(self.group_id, limit=limit, end_time=current_end_time)

            if result.get("rate_limited"):
                print(f"[WARNING] 触发风控: {result.get('rate_limit_msg', '操作过于频繁')}")
                print(f"[WARNING] 已获取 {len(all_topics)} 条，程序停止以保护账号")
                break
            if not result["success"]:
                print(f"[ERROR] 获取主题失败")
                break

            topics = result["topics"]
            if not topics:
                break

            all_topics.extend(topics)
            remaining -= len(topics)

            if not result["has_more"]:
                break

            current_end_time = result["next_end_time"]
            print(f"  [DEBUG] 翻页: end_time={current_end_time}, 已获取 {len(all_topics)} 条")

        return all_topics

    def get_all_topics_since(self, since_time):
        """
        获取指定时间之后的所有主题（增量爬取，自动翻页）

        Args:
            since_time: ISO 格式的时间字符串

        Returns:
            list: 主题列表，按时间倒序排列
        """
        print(f"[INFO] 获取 {since_time} 之后的所有新主题...")
        since_dt = self.parse_time(since_time)
        if not since_dt:
            print(f"[ERROR] 无法解析时间格式: {since_time}")
            return []

        all_topics = []
        end_time = None
        reached_old = False

        for page in range(MAX_PAGES):
            print(f"  获取第 {page + 1} 页...")
            result = self.client.get_topics(self.group_id, limit=MAX_TOPICS_PER_PAGE, end_time=end_time)

            if result.get("rate_limited"):
                print(f"[WARNING] 触发风控: {result.get('rate_limit_msg', '操作过于频繁')}")
                print(f"[WARNING] 已获取 {len(all_topics)} 条，程序停止以保护账号")
                break
            if not result["success"]:
                print(f"[WARN] 请求失败，停止获取")
                break

            topics = result["topics"]
            if not topics:
                print(f"[INFO] 没有更多内容")
                break

            page_new_count = 0
            page_old_count = 0

            for topic in topics:
                create_time = topic.get("create_time", "")
                dt = self.parse_time(create_time)
                if not dt:
                    continue
                if dt > since_dt:
                    all_topics.append(topic)
                    page_new_count += 1
                else:
                    page_old_count += 1

            print(f"  本页统计: {page_new_count} 条新内容, {page_old_count} 条旧内容")

            # 更新分页游标
            if topics:
                end_time = topics[-1].get("create_time")

            # 终止条件
            if page_new_count > 0 and page_old_count > 0:
                print(f"  已到达上次爬取时间点，停止获取")
                break
            if page_new_count == 0 and page_old_count > 0:
                print(f"  本页全是旧内容，停止获取")
                break
            if not result["has_more"]:
                print(f"  没有更多页面")
                break

        print(f"[INFO] 共找到 {len(all_topics)} 条新主题")
        return all_topics

    def get_today_topics(self):
        """获取今天所有的主题内容（支持翻页）"""
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"[INFO] 获取 {today} 的所有主题...")

        all_topics = []
        end_time = None

        for page in range(MAX_PAGES):
            print(f"  获取第 {page + 1} 页...")
            result = self.client.get_topics(self.group_id, limit=MAX_TOPICS_PER_PAGE, end_time=end_time)

            if not result["success"]:
                break

            topics = result["topics"]
            if not topics:
                break

            found_today = False
            for topic in topics:
                create_time = topic.get("create_time", "")
                try:
                    dt = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                    topic_date = dt.strftime("%Y-%m-%d")
                except:
                    continue

                if topic_date == today:
                    all_topics.append(topic)
                    found_today = True
                elif topic_date < today:
                    print(f"  已到达昨天 ({topic_date})，停止获取")
                    return all_topics

            if not found_today:
                print(f"  本页没有今天的内容，停止获取")
                break

            # 更新游标
            if topics:
                end_time = topics[-1].get("create_time")

            if not result["has_more"]:
                break

        return all_topics

    def get_topics_by_date(self, target_date_str):
        """
        获取指定日期的所有主题内容（支持翻页）

        Args:
            target_date_str: 日期字符串，格式 "YYYY-MM-DD"

        Returns:
            list: 主题列表
        """
        print(f"[INFO] 获取 {target_date_str} 的所有主题...")

        all_topics = []
        end_time = None
        reached_previous_day = False
        rate_limited = False

        for page in range(MAX_PAGES):
            print(f"\n[第 {page + 1} 页] 请求中...")
            result = self.client.get_topics(self.group_id, limit=MAX_TOPICS_PER_PAGE, end_time=end_time)

            if result.get("rate_limited"):
                print(f"[WARNING] 触发风控: {result.get('rate_limit_msg', '操作过于频繁')}")
                print(f"[WARNING] 已获取 {len(all_topics)} 条，程序停止")
                rate_limited = True
                break

            if not result["success"]:
                print(f"[ERROR] 获取主题失败")
                break

            topics = result["topics"]
            if not topics:
                break

            page_target_count = 0
            page_other_count = 0
            found_older = False

            for topic in topics:
                create_time = topic.get("create_time", "")
                try:
                    dt = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                    topic_date = dt.strftime("%Y-%m-%d")
                except:
                    continue

                if topic_date == target_date_str:
                    all_topics.append(topic)
                    page_target_count += 1
                elif topic_date < target_date_str:
                    # 已经到达目标日期之前
                    found_older = True
                else:
                    page_other_count += 1

            print(f"  本页: 目标日期 {page_target_count} 条, 其他日期 {page_other_count} 条")
            print(f"  累计 {target_date_str}: {len(all_topics)} 条")

            if topics:
                end_time = topics[-1].get("create_time")

            if not result["has_more"]:
                print(f"  [INFO] 没有更多页面")
                break

            # 修改：只有当找到更旧的日期且当前页没有目标日期时才停止
            if found_older and page_target_count == 0:
                print(f"  [INFO] 已到达 {target_date_str} 之前的内容，停止获取")
                break

        print("\n" + "=" * 60)
        print(f"[完成] {target_date_str} 共获取 {len(all_topics)} 条主题")
        if rate_limited:
            print(f"[注意] 因触发风控提前停止，可能未获取完整")
        return all_topics

    def clean_content(self, text):
        """清理内容文本，转换为 Markdown 格式，保留内嵌链接"""
        if not text:
            return ""
        import html
        from urllib.parse import unquote
        
        # 处理 <e type="text_bold" title="..." /> 格式（加粗标题）
        def replace_text_bold(match):
            title = match.group(1)
            title = unquote(title)
            return f"**{title}**"
        
        text = re.sub(r'<e\b[^>]*?\btype=["\']text_bold["\'][^>]*?\btitle=["\']([^"\']*)["\'][^>]*?/>', replace_text_bold, text)
        
        # 处理 <e type="web" href="..." title="..." /> 格式的内嵌链接（知识星球自定义标签）
        # 属性顺序可能不同，使用非贪婪匹配
        def replace_e_tag(match):
            href = match.group(1)
            title = match.group(2)
            # URL 解码
            href = unquote(href)
            title = unquote(title)
            return f"[{title}]({href})"
        
        text = re.sub(r'<e\b[^>]*?\btype=["\']web["\'][^>]*?\bhref=["\']([^"\']+)["\'][^>]*?\btitle=["\']([^"\']*)["\'][^>]*?/>', replace_e_tag, text)
        # 再处理一次 title 在 href 前面的情况
        text = re.sub(r'<e\b[^>]*?\btype=["\']web["\'][^>]*?\btitle=["\']([^"\']*)["\'][^>]*?\bhref=["\']([^"\']+)["\'][^>]*?/>', lambda m: f"[{unquote(m.group(1))}]({unquote(m.group(2))})", text)
        
        # 处理 <a> 标签
        def replace_a_tag(match):
            href = match.group(1)
            title = match.group(2)
            href = unquote(href)
            return f"[{title}]({href})"
        
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', replace_a_tag, text)
        
        # 移除其他 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 解码 HTML 实体
        text = html.unescape(text)
        
        # 规范化换行
        text = text.replace('\n\n', '\n')
        return text.strip()
    
    def fetch_inline_article(self, article_info):
        """
        获取内嵌文章的完整内容
        
        Args:
            article_info: talk.article 字典，包含 inline_article_url
        
        Returns:
            str: 文章正文（Markdown格式），失败返回空字符串
        """
        if not article_info or not isinstance(article_info, dict):
            return ""
        
        inline_url = article_info.get("inline_article_url", "")
        if not inline_url:
            return ""
        
        try:
            import requests
            from html import unescape
            
            # 使用认证过的session（如果client有的话）
            if hasattr(self.client, 'session') and self.client.session:
                response = self.client.session.get(inline_url, timeout=15)
            else:
                response = requests.get(inline_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }, timeout=15)
            
            if response.status_code != 200:
                return ""
            
            html_text = response.text
            
            # 提取 ql-editor 中的内容
            match = re.search(r'<div class="content ql-editor">(.*?)</div>\s*</div>\s*<div class="milkdown-preview">', html_text, re.DOTALL)
            if not match:
                # 尝试备用匹配
                match = re.search(r'<div class="content ql-editor">(.*?)</div>', html_text, re.DOTALL)
            
            if not match:
                return ""
            
            content_html = match.group(1)
            
            # 将HTML转换为Markdown
            md_content = self._html_to_markdown(content_html)
            return md_content
            
        except Exception as e:
            print(f"[WARN] 获取内嵌文章失败: {e}")
            return ""
    
    def download_file(self, file_url, file_name, output_dir):
        """
        下载附件文件到指定目录
        
        Args:
            file_url: 文件下载链接
            file_name: 保存的文件名
            output_dir: 输出目录（multimedia文件夹）
        
        Returns:
            str: 本地文件路径，失败返回空字符串
        """
        if not file_url or not file_name:
            return ""
        
        try:
            import requests
            from pathlib import Path
            
            # 确保输出目录存在
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 清理文件名
            safe_name = re.sub(r'[\u003c\u003e:"/\\|?*]', '_', file_name)
            file_path = output_path / safe_name
            
            # 检查文件是否已存在
            if file_path.exists():
                print(f"[INFO] 文件已存在，跳过下载: {safe_name}")
                return str(file_path)
            
            # 下载文件
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            # 如果有认证session，使用它
            if hasattr(self.client, 'session') and self.client.session:
                response = self.client.session.get(file_url, headers=headers, timeout=60, stream=True)
            else:
                response = requests.get(file_url, headers=headers, timeout=60, stream=True)
            
            if response.status_code != 200:
                print(f"[WARN] 下载文件失败，HTTP {response.status_code}: {safe_name}")
                return ""
            
            # 保存文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[SUCCESS] 已下载文件: {safe_name} ({file_path.stat().st_size} bytes)")
            return str(file_path)
            
        except Exception as e:
            print(f"[WARN] 下载文件失败: {e}")
            return ""
        """
        下载附件文件到指定目录
        
        Args:
            file_url: 文件下载链接
            file_name: 保存的文件名
            output_dir: 输出目录（multimedia文件夹）
        
        Returns:
            str: 本地文件路径，失败返回空字符串
        """
        if not file_url or not file_name:
            return ""
        
        try:
            import requests
            from pathlib import Path
            
            # 确保输出目录存在
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 清理文件名
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)
            file_path = output_path / safe_name
            
            # 检查文件是否已存在
            if file_path.exists():
                print(f"[INFO] 文件已存在，跳过下载: {safe_name}")
                return str(file_path)
            
            # 下载文件
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            # 如果有认证session，使用它
            if hasattr(self.client, 'session') and self.client.session:
                response = self.client.session.get(file_url, headers=headers, timeout=60, stream=True)
            else:
                response = requests.get(file_url, headers=headers, timeout=60, stream=True)
            
            if response.status_code != 200:
                print(f"[WARN] 下载文件失败，HTTP {response.status_code}: {safe_name}")
                return ""
            
            # 保存文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[SUCCESS] 已下载文件: {safe_name} ({file_path.stat().st_size} bytes)")
            return str(file_path)
            
        except Exception as e:
            print(f"[WARN] 下载文件失败: {e}")
            return ""
    
    def _html_to_markdown(self, html_content):
        """
        将HTML内容转换为Markdown
        
        Args:
            html_content: HTML字符串
        
        Returns:
            str: Markdown字符串
        """
        from html import unescape
        from urllib.parse import unquote
        
        text = html_content
        
        # 处理 <p><strong>...</strong></p> → **...**
        text = re.sub(r'<p>\s*<strong>(.*?)</strong>\s*</p>', r'\n**\1**\n', text, flags=re.DOTALL)
        
        # 处理 <p>...</p> → 段落
        text = re.sub(r'<p>(.*?)</p>', r'\n\1\n', text, flags=re.DOTALL)
        
        # 处理 <strong>...</strong> → **...**
        text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
        
        # 处理 <em>...</em> → *...*
        text = re.sub(r'<em>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
        
        # 处理 <br> / <br/> → 换行
        text = re.sub(r'<br\s*/?>', '\n', text)
        
        # 处理 <a href="...">...</a> → [...](...)
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', lambda m: f"[{m.group(2)}]({m.group(1)})", text, flags=re.DOTALL)
        
        # 移除其他HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 解码HTML实体
        text = unescape(text)
        
        # 规范化空白
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        return text

    def extract_urls(self, text):
        """从文本中提取所有 URL（内嵌链接）"""
        if not text:
            return []
        # 匹配 Markdown 链接
        md_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
        # 匹配纯 URL
        raw_urls = re.findall(r'https?://[^\s<>"\')\]]+', text)
        result = []
        for title, url in md_links:
            result.append({"title": title, "url": url})
        for url in raw_urls:
            # 去重
            if not any(u["url"] == url for u in result):
                result.append({"title": "", "url": url})
        return result

    def parse_topic(self, topic):
        """
        解析单个主题内容
        适配 zsxq-cli 输出的扁平化数据结构
        """
        topic_id = topic.get("topic_id") or topic.get("id")
        if topic_id is None:
            topic_id = str(int(time.time() * 1000000))

        result = {
            "id": str(topic_id),
            "type": topic.get("type"),
            "create_time": topic.get("create_time"),
            "title": topic.get("title", ""),
            "content": "",
            "author": {},
            "images": [],
            "files": [],
            "comments": [],
            "urls": [],
            "likes_count": 0,
            "comments_count": 0,
        }

        # 作者信息
        owner = topic.get("owner", {})
        result["author"] = {
            "name": owner.get("name", "未知"),
            "avatar": owner.get("avatar_url", ""),
        }

        # 内容（zsxq-cli 已扁平化，直接取 content）
        raw_content = topic.get("content", "")
        cleaned_content = self.clean_content(raw_content)
        
        # 提取内嵌链接
        result["urls"] = self.extract_urls(raw_content)
        
        # 处理内嵌文章 - 如果有article信息，获取完整内容
        talk = topic.get("talk", {}) or {}
        full_article = ""
        if isinstance(talk, dict) and talk.get("article"):
            article_info = talk["article"]
            article_url = article_info.get("article_url", "")
            article_title = article_info.get("title", "")
            if article_url:
                result["urls"].append({"title": article_title or "阅读原文", "url": article_url})
            
            # 获取内嵌文章的完整内容
            full_article = self.fetch_inline_article(article_info)
            if full_article:
                print(f"[INFO] 已获取内嵌文章完整内容: {article_title}")
        
        # 如果获取了完整文章，且原始内容只是摘要（很短或被截断），则用完整文章替换
        if full_article and (len(cleaned_content) < 500 or cleaned_content.rstrip().endswith('...')):
            result["content"] = full_article
        elif full_article:
            result["content"] = cleaned_content + "\n\n---\n\n" + full_article
        else:
            result["content"] = cleaned_content

        # 互动数据（counts 结构）
        counts = topic.get("counts", {})
        result["likes_count"] = counts.get("likes", 0)
        result["comments_count"] = counts.get("comments", 0)

        # 图片（扁平化结构中 images 在顶层）
        images = topic.get("images", [])
        for img in images:
            if isinstance(img, dict):
                url = img.get("large", {}).get("url", "") if img.get("large") else img.get("url", "")
                if url:
                    result["images"].append({
                        "url": url,
                        "name": img.get("name", ""),
                    })

        # 文件
        files = topic.get("files", [])
        for f in files:
            if isinstance(f, dict):
                result["files"].append({
                    "name": f.get("name", ""),
                    "url": f.get("url", ""),
                    "size": f.get("size", 0),
                })

        # 评论（如果 topic 中包含 show_comments）
        comments = topic.get("show_comments", [])
        for comment in comments:
            if isinstance(comment, dict):
                c_owner = comment.get("owner", {})
                result["comments"].append({
                    "author": c_owner.get("name", "未知"),
                    "content": self.clean_content(comment.get("text", "")),
                    "create_time": comment.get("create_time"),
                })

        return result

    def save_to_obsidian(self, topic_data, multimedia_dir=None):
        """保存主题到 Obsidian"""
        create_time = topic_data.get("create_time", "")
        topic_id = topic_data.get("id") or str(int(time.time() * 1000))

        try:
            dt = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        except:
            date_str = datetime.now().strftime("%Y-%m-%d")
            time_str = datetime.now().strftime("%H:%M")

        title = topic_data.get("title", "")[:30]
        if title:
            safe_title = re.sub(r'[\\/*?#:"<>|\n\r]', "_", title)
            safe_title = safe_title.strip()  # 移除前后空格
            safe_title = re.sub(r'\s+', "_", safe_title)  # 将空格替换为下划线
            filename = f"{date_str}_{safe_title}_{topic_id[-6:]}.md"
        else:
            content = topic_data.get("content", "")[:20]
            safe_content = re.sub(r'[\\/*?#:"<>|\n\r]', "_", content)
            safe_content = safe_content.strip()  # 移除前后空格
            safe_content = re.sub(r'\s+', "_", safe_content)  # 将空格替换为下划线
            filename = f"{date_str}_{safe_content}_{topic_id[-6:]}.md"

        filepath = os.path.join(self.zsxq_folder, filename)

        content_lines = [
            "---",
            f"title: {topic_data.get('title', '无标题')}",
            f"date: {date_str}",
            f"time: {time_str}",
            f"author: {topic_data.get('author', {}).get('name', '未知')}",
            f"type: {topic_data.get('type', 'unknown')}",
            f"likes: {topic_data.get('likes_count', 0)}",
            f"comments: {topic_data.get('comments_count', 0)}",
            f"source: https://wx.zsxq.com/group/{self.group_id}/topic/{topic_id}",
            "---",
            "",
        ]

        content_text = topic_data.get("content", "")
        if content_text:
            content_lines.append(content_text)
            content_lines.append("")

        images = topic_data.get("images", [])
        if images:
            content_lines.append("## 图片")
            for img in images:
                img_url = img.get("url", "")
                if img_url:
                    content_lines.append(f"![]({img_url})")
            content_lines.append("")

        files = topic_data.get("files", [])
        if files:
            content_lines.append("## 附件")
            for f in files:
                name = f.get("name", "")
                url = f.get("url", "")
                if url:
                    content_lines.append(f"- [{name}]({url})")
            content_lines.append("")
            
            # 下载PDF等文件到multimedia目录
            if multimedia_dir:
                downloaded_files = []
                for f in files:
                    file_url = f.get("url", "")
                    file_name = f.get("name", "")
                    if file_url and file_name:
                        # 检查是否是PDF或其他可下载文件
                        ext = os.path.splitext(file_name)[1].lower()
                        if ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']:
                            local_path = self.download_file(file_url, file_name, multimedia_dir)
                            if local_path:
                                downloaded_files.append((file_name, local_path))
                
                if downloaded_files:
                    content_lines.append("## 本地附件")
                    for name, path in downloaded_files:
                        content_lines.append(f"- {name}: `{path}`")
                    content_lines.append("")

        # 内嵌链接
        urls = topic_data.get("urls", [])
        if urls:
            content_lines.append("## 链接")
            for u in urls:
                title = u.get("title", "")
                url = u.get("url", "")
                if title and url:
                    content_lines.append(f"- [{title}]({url})")
                elif url:
                    content_lines.append(f"- {url}")
            content_lines.append("")

        comments = topic_data.get("comments", [])
        if comments:
            content_lines.append("## 评论")
            for comment in comments:
                author = comment.get("author", "未知")
                text = comment.get("content", "")
                content_lines.append(f"**{author}**: {text}")
                content_lines.append("")

        full_content = "\n".join(content_lines)

        original_filepath = filepath
        counter = 1
        while os.path.exists(filepath):
            name, ext = os.path.splitext(original_filepath)
            filepath = f"{name}_{counter}{ext}"
            counter += 1

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        print(f"[SUCCESS] 已保存: {os.path.basename(filepath)}")
        return filepath

    def parse_time(self, time_str):
        """解析时间字符串"""
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except:
            pass
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except:
                continue
        return None

    def run(self, count=10, today_only=True, incremental=True, test_mode=False, multimedia_dir=None):
        """运行爬虫"""
        print("=" * 50)
        print("知识星球爬虫启动 (zsxq-cli 版本)")
        print(f"目标群组: {self.group_id}")
        if test_mode:
            print("测试模式: 获取所有内容（不更新时间戳）")
        elif incremental:
            last_time = self.get_last_crawl_time()
            print(f"增量爬取: 获取 {last_time} 之后的新内容")
        elif today_only:
            print(f"获取范围: 今天 ({datetime.now().strftime('%Y-%m-%d')}) 的所有内容")
        else:
            print(f"获取数量: 最近 {count} 条")
        if multimedia_dir:
            print(f"附件下载目录: {multimedia_dir}")
        print("=" * 50)

        # 1. 检查认证并获取星球信息
        print("\n[1/3] 检查认证并获取星球信息...")
        if not self.check_auth():
            return False

        group_info = self.get_group_info()
        if group_info:
            print(f"  星球名称: {group_info.get('name')}")
        else:
            print("  [WARN] 无法获取星球信息，但会继续尝试获取内容")

        time.sleep(2)

        # 2. 获取主题列表
        if test_mode:
            print(f"\n[2/3] 测试模式：获取最近 100 条主题...")
            topics = self.get_topics(count=100)
        elif incremental:
            print(f"\n[2/3] 增量获取新主题...")
            last_time = self.get_last_crawl_time()
            topics = self.get_all_topics_since(last_time)
        elif today_only:
            print(f"\n[2/3] 获取今天所有主题...")
            topics = self.get_today_topics()
        else:
            print(f"\n[2/3] 获取最近 {count} 条主题...")
            topics = self.get_topics(count=count)

        if not topics:
            print("  [INFO] 没有新内容需要爬取")
            return True

        print(f"  成功获取 {len(topics)} 条主题")

        print(f"\n[DEBUG] 前3条主题的时间信息:")
        for i, topic in enumerate(topics[:3]):
            print(f"  [{i+1}] {topic.get('create_time')} - {topic.get('type')} - ID:{topic.get('topic_id')}")

        # 3. 解析并保存
        print(f"\n[3/3] 保存到 Obsidian...")
        saved_count = 0
        latest_time = None

        for topic in topics:
            try:
                parsed = self.parse_topic(topic)
                self.save_to_obsidian(parsed, multimedia_dir=multimedia_dir)
                saved_count += 1

                create_time = topic.get("create_time")
                if create_time:
                    if latest_time is None or create_time > latest_time:
                        latest_time = create_time
            except Exception as e:
                print(f"  [ERROR] 保存主题失败: {e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"\n[SUCCESS] 共保存 {saved_count}/{len(topics)} 条笔记")
        print(f"保存位置: {self.zsxq_folder}")

        # 4. 保存最新时间戳（测试模式不保存）
        if latest_time and incremental and not test_mode:
            self.save_last_crawl_time(latest_time)

        return True


def main():
    """主函数"""
    print("知识星球爬虫 (zsxq-cli 版本)")
    print("-" * 50)

    test_mode = "--test" in sys.argv
    recent_mode = "--recent" in sys.argv
    
    # 解析multimedia目录参数
    multimedia_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == "--multimedia" and i + 1 < len(sys.argv):
            multimedia_dir = sys.argv[i + 1]
            break

    try:
        spider = ZsxqSpider()
    except ZsxqCliError as e:
        print(f"[ERROR] {e}")
        return

    if test_mode:
        print("[INFO] 启动测试模式（获取最近100条，不更新时间戳）")
        spider.run(test_mode=True, multimedia_dir=multimedia_dir)
    elif recent_mode:
        print("[INFO] 启动近期模式（获取最近100条）")
        spider.run(count=100, today_only=False, incremental=False, multimedia_dir=multimedia_dir)
    else:
        print("[INFO] 启动增量爬取模式")
        spider.run(incremental=True, multimedia_dir=multimedia_dir)


if __name__ == "__main__":
    main()
