#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球爬虫主程序（按日期爬取）
爬取指定日期的所有帖子，保存为Markdown文件。
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import GROUP_ID, OUTPUT_DIR, MULTIMEDIA_DIR, REQUEST_DELAY, MAX_TOPICS_PER_PAGE, MAX_PAGES
from api_client import ZsxqApiClient, ZsxqApiError


def sanitize_filename(text):
    """清理文件名中的非法字符"""
    if not text:
        return "untitled"
    # 移除非法字符
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    # 移除前后空白
    text = text.strip()
    # 限制长度
    if len(text) > 100:
        text = text[:100]
    return text


def parse_topic_to_markdown(topic, client=None, multimedia_dir=None):
    """
    将知识星球主题解析为Markdown格式
    
    Args:
        topic: 主题字典
        client: 可选的API客户端，用于获取内嵌文章完整内容
        multimedia_dir: 可选的附件下载目录
    
    Returns:
        dict: {
            "frontmatter": str,
            "content": str,
            "title": str,
            "date": str,
            "time": str,
            "author": str,
            "type": str,
            "likes": int,
            "comments": int,
            "source": str,
            "downloaded_files": list,  # 已下载的本地文件路径
        }
    """
    topic_id = topic.get("topic_id", "")
    title = topic.get("title", "") or "无标题"
    
    # 获取正文内容 - 知识星球API中talk类型的内容在talk.text字段
    content = topic.get("content", "") or ""
    talk = topic.get("talk", {}) or {}
    if isinstance(talk, dict):
        if not content:
            content = talk.get("text", "") or ""
        if not content:
            content = talk.get("content", "") or ""
    
    # 获取作者信息 - 在talk.owner中
    author = "未知作者"
    if isinstance(talk, dict):
        talk_owner = talk.get("owner")
        if talk_owner and isinstance(talk_owner, dict):
            author = talk_owner.get("name", "未知作者")
    if author == "未知作者":
        author = topic.get("owner", {}).get("name", "未知作者")
    
    create_time = topic.get("create_time", "")
    topic_type = topic.get("type", "talk")
    likes = topic.get("likes_count", 0)
    comments = topic.get("comments_count", 0)
    
    # 获取图片 - 在talk.images中
    images = topic.get("images", []) or []
    if isinstance(talk, dict):
        talk_images = talk.get("images", [])
        if talk_images:
            images = talk_images
    
    # 获取附件 - 在talk.files中
    files = topic.get("files", []) or []
    if isinstance(talk, dict):
        talk_files = talk.get("files", [])
        if talk_files:
            files = talk_files
    
    # 解析时间
    dt = None
    if create_time:
        try:
            # 尝试解析ISO格式
            dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
            dt = dt.astimezone(timezone(timedelta(hours=8)))  # 转为北京时间
        except:
            dt = datetime.now(timezone(timedelta(hours=8)))
    else:
        dt = datetime.now(timezone(timedelta(hours=8)))
    
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")
    
    # 构建frontmatter
    frontmatter = f"""---
title: {title}
date: {date_str}
time: {time_str}
author: {author}
type: {topic_type}
likes: {likes}
comments: {comments}
source: https://wx.zsxq.com/dweb2/index/topic_detail/{topic_id}
---

"""
    
    # 构建内容
    md_content = f"# {title}\n\n"
    md_content += f"**作者**: {author}  \n"
    md_content += f"**时间**: {date_str} {time_str}  \n"
    md_content += f"**点赞**: {likes} | **评论**: {comments}  \n"
    md_content += f"**链接**: [原文](https://wx.zsxq.com/dweb2/index/topic_detail/{topic_id})  \n\n"
    md_content += "---\n\n"
    
    # 处理内嵌文章 - 获取完整内容
    full_article_content = ""
    article_info = talk.get("article") if isinstance(talk, dict) else None
    if article_info and isinstance(article_info, dict):
        article_url = article_info.get("article_url", "")
        article_title = article_info.get("title", "")
        article_id = article_info.get("article_id", "")
        if article_url:
            md_content += f"**文章链接**: [阅读原文]({article_url})\n\n"
        
        # 尝试获取inline article的完整内容
        inline_url = article_info.get("inline_article_url", f"https://articles.zsxq.com/inline_form/id_{article_id}.html")
        if client and hasattr(client, 'session') and client.session:
            try:
                import requests
                from html import unescape
                
                response = client.session.get(inline_url, timeout=15)
                if response.status_code == 200:
                    # 提取 ql-editor 中的内容
                    match = re.search(r'<div class="content ql-editor">(.*?)</div>\s*</div>\s*<div class="milkdown-preview">', response.text, re.DOTALL)
                    if not match:
                        match = re.search(r'<div class="content ql-editor">(.*?)</div>', response.text, re.DOTALL)
                    
                    if match:
                        content_html = match.group(1)
                        # 将HTML转换为Markdown
                        article_md = content_html
                        
                        # 处理 <p><strong>...</strong></p> → **...**
                        article_md = re.sub(r'<p>\s*<strong>(.*?)</strong>\s*</p>', r'\n**\1**\n', article_md, flags=re.DOTALL)
                        
                        # 处理 <p>...</p> → 段落
                        article_md = re.sub(r'<p>(.*?)</p>', r'\n\1\n', article_md, flags=re.DOTALL)
                        
                        # 处理 <strong>...</strong> → **...**
                        article_md = re.sub(r'<strong>(.*?)</strong>', r'**\1**', article_md, flags=re.DOTALL)
                        
                        # 处理 <em>...</em> → *...*
                        article_md = re.sub(r'<em>(.*?)</em>', r'*\1*', article_md, flags=re.DOTALL)
                        
                        # 处理 <br> / <br/> → 换行
                        article_md = re.sub(r'<br\s*/?>', '\n', article_md)
                        
                        # 处理 <a href="...">...</a> → [...](...)
                        article_md = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', lambda m: f"[{m.group(2)}]({m.group(1)})", article_md, flags=re.DOTALL)
                        
                        # 移除其他HTML标签
                        article_md = re.sub(r'<[^>]+>', '', article_md)
                        
                        # 解码HTML实体
                        article_md = unescape(article_md)
                        
                        # 规范化空白
                        article_md = re.sub(r'\n{3,}', '\n\n', article_md)
                        article_md = article_md.strip()
                        
                        if article_md:
                            full_article_content = article_md
                            print(f"[INFO] 已获取内嵌文章完整内容: {article_title}")
            except Exception as e:
                print(f"[WARN] 获取内嵌文章失败: {e}")
    
    # 添加正文内容（清理HTML标签）
    if content:
        # 处理 <e type="text_bold" title="..." /> 格式
        import html
        from urllib.parse import unquote
        
        def replace_text_bold(match):
            title = match.group(1)
            title = unquote(title)
            return f"**{title}**"
        
        content = re.sub(r'<e\b[^>]*?\btype=["\']text_bold["\'][^>]*?\btitle=["\']([^"\']*)["\'][^>]*?/>', replace_text_bold, content)
        
        # 处理 <e type="web" href="..." title="..." /> 格式的内嵌链接
        def replace_e_tag(match):
            href = match.group(1)
            title = match.group(2)
            href = unquote(href)
            title = unquote(title)
            return f"[{title}]({href})"
        
        content = re.sub(r'<e\b[^>]*?\btype=["\']web["\'][^>]*?\bhref=["\']([^"\']+)["\'][^>]*?\btitle=["\']([^"\']*)["\'][^>]*?/>', replace_e_tag, content)
        content = re.sub(r'<e\b[^>]*?\btype=["\']web["\'][^>]*?\btitle=["\']([^"\']*)["\'][^>]*?\bhref=["\']([^"\']+)["\'][^>]*?/>', lambda m: f"[{unquote(m.group(1))}]({unquote(m.group(2))})", content)
        
        # 处理 <a> 标签
        content = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', lambda m: f"[{m.group(2)}]({m.group(1)})", content)
        
        # 移除其他HTML标签
        content = re.sub(r'<[^>]+>', '', content)
        
        # 解码HTML实体
        content = html.unescape(content)
        
        # 如果获取了完整内嵌文章，且content只是摘要（很短或被截断），则跳过摘要
        if full_article_content and (len(content) < 500 or '...' in content[-10:]):
            pass  # 跳过摘要，只使用完整文章
        else:
            md_content += content + "\n\n"
    
    # 如果有内嵌文章完整内容，添加分隔线后追加
    if full_article_content:
        if md_content.endswith("\n\n"):
            md_content = md_content.rstrip() + "\n\n---\n\n"
        else:
            md_content += "\n\n---\n\n"
        md_content += full_article_content + "\n\n"
    
    # 处理图片
    if images:
        md_content += "## 图片\n\n"
        for img in images:
            img_url = img.get("large", {}).get("url", "") or img.get("url", "")
            if img_url:
                md_content += f"![图片]({img_url})\n\n"
    
    # 处理附件
    downloaded_files = []
    if files:
        md_content += "## 附件\n\n"
        for f in files:
            file_name = f.get("name", "附件")
            file_url = f.get("url", "")
            if file_url:
                md_content += f"- [{file_name}]({file_url})\n"
        md_content += "\n"
        
        # 下载PDF等文件到multimedia目录
        if multimedia_dir and client:
            from pathlib import Path
            
            multimedia_path = Path(multimedia_dir)
            multimedia_path.mkdir(parents=True, exist_ok=True)
            
            for f in files:
                file_url = f.get("url", "")
                file_name = f.get("name", "")
                if file_url and file_name:
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']:
                        try:
                            safe_name = re.sub(r'[<>"/\\|?*]', '_', file_name)
                            file_path = multimedia_path / safe_name
                            
                            if file_path.exists():
                                print(f"[INFO] 文件已存在，跳过下载: {safe_name}")
                                downloaded_files.append(str(file_path))
                                continue
                            
                            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                            if hasattr(client, 'session') and client.session:
                                response = client.session.get(file_url, headers=headers, timeout=60, stream=True)
                            else:
                                import requests
                                response = requests.get(file_url, headers=headers, timeout=60, stream=True)
                            
                            # 如果404，尝试通过 download_url API 获取真实下载链接
                            if response.status_code == 404:
                                print(f"[INFO] 尝试通过 download_url API 获取下载链接...")
                                download_url_api = f"https://api.zsxq.com/v2/files/{f.get('file_id', '')}/download_url"
                                if hasattr(client, 'session') and client.session:
                                    resp = client.session.get(download_url_api, headers=headers, timeout=30)
                                else:
                                    import requests
                                    resp = requests.get(download_url_api, headers=headers, timeout=30)
                                
                                if resp.status_code == 200:
                                    try:
                                        data = resp.json()
                                        if data.get("succeeded") and data.get("resp_data", {}).get("download_url"):
                                            real_download_url = data["resp_data"]["download_url"]
                                            print(f"[INFO] 获取到下载链接: {real_download_url[:100]}...")
                                            # 重新下载
                                            if hasattr(client, 'session') and client.session:
                                                response = client.session.get(real_download_url, headers=headers, timeout=60, stream=True)
                                            else:
                                                import requests
                                                response = requests.get(real_download_url, headers=headers, timeout=60, stream=True)
                                        else:
                                            print(f"[WARN] download_url API 返回无效数据")
                                    except Exception as e:
                                        print(f"[WARN] 解析 download_url API 响应失败: {e}")
                                else:
                                    print(f"[WARN] download_url API 返回 HTTP {resp.status_code}")
                            
                            if response.status_code == 200:
                                with open(file_path, 'wb') as fp:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            fp.write(chunk)
                                print(f"[SUCCESS] 已下载文件: {safe_name} ({file_path.stat().st_size} bytes)")
                                downloaded_files.append(str(file_path))
                            else:
                                print(f"[WARN] 下载文件失败，HTTP {response.status_code}: {safe_name}")
                        except Exception as e:
                            print(f"[WARN] 下载文件失败: {e}")
            
            if downloaded_files:
                md_content += "## 本地附件\n\n"
                for path in downloaded_files:
                    md_content += f"- `{path}`\n"
                md_content += "\n"
    
    # 处理评论预览
    if comments > 0:
        md_content += f"## 评论 ({comments}条)\n\n"
        md_content += "*（完整评论请查看原文）*\n\n"
    
    return {
        "frontmatter": frontmatter,
        "content": md_content,
        "title": title,
        "date": date_str,
        "time": time_str,
        "author": author,
        "type": topic_type,
        "likes": likes,
        "comments": comments,
        "source": f"https://wx.zsxq.com/dweb2/index/topic_detail/{topic_id}",
        "downloaded_files": downloaded_files,
    }


def save_topic_to_file(topic_data, output_dir):
    """
    保存主题到Markdown文件
    
    Args:
        topic_data: 解析后的主题数据
        output_dir: 输出目录
    
    Returns:
        Path: 保存的文件路径
    """
    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 构建文件名: {日期}_{标题}_{ID后6位}.md
    safe_title = sanitize_filename(topic_data["title"])
    # 从source中提取topic_id
    topic_id = topic_data["source"].split("/")[-1]
    id_suffix = topic_id[-6:] if len(topic_id) >= 6 else topic_id
    
    filename = f"{topic_data['date']}_{safe_title}_{id_suffix}.md"
    file_path = output_path / filename
    
    # 写入文件
    full_content = topic_data["frontmatter"] + topic_data["content"]
    file_path.write_text(full_content, encoding="utf-8")
    
    return file_path


def fetch_topics_by_date(client, group_id, target_date, max_pages=MAX_PAGES):
    """
    按日期获取所有主题 - 使用默认scope（不带scope参数）翻页获取
    
    Args:
        client: ZsxqApiClient实例
        group_id: 星球ID
        target_date: 目标日期 (YYYY-MM-DD)
        max_pages: 最大翻页数
    
    Returns:
        list: 该日期的所有主题列表
    """
    target_topics = []
    end_time = None
    page = 0
    crossed_date = False  # 标记是否已经越过目标日期
    
    # 解析目标日期
    target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(
        tzinfo=timezone(timedelta(hours=8))
    )
    target_start = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    target_end = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    print(f"[INFO] 开始爬取 {target_date} 的帖子...")
    print(f"[INFO] 时间范围: {target_start.isoformat()} ~ {target_end.isoformat()}")
    
    while page < max_pages:
        page += 1
        print(f"[INFO] 获取第 {page} 页...", end=" ")
        
        # 使用默认scope（不带scope参数），增加重试机制
        max_retries = 5
        result = None
        for attempt in range(max_retries):
            result = client.get_topics(group_id, limit=MAX_TOPICS_PER_PAGE, end_time=end_time)
            if result["success"]:
                break
            if attempt < max_retries - 1:
                print(f"失败 (API错误，重试 {attempt + 1}/{max_retries})...", end=" ")
                import time
                time.sleep(3)
        
        if not result or not result["success"]:
            print(f"失败 (API错误，已重试{max_retries}次)")
            break
        
        topics = result["topics"]
        if not topics:
            print(f"无数据")
            break
        
        print(f"获取 {len(topics)} 条")
        
        # 筛选目标日期的帖子
        found_in_range = False
        all_before_target = True  # 标记是否全部早于目标日期
        
        for topic in topics:
            create_time = topic.get("create_time", "")
            if not create_time:
                continue
            
            try:
                topic_dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
                topic_dt = topic_dt.astimezone(timezone(timedelta(hours=8)))
            except:
                continue
            
            # 检查是否在目标日期范围内
            if target_start <= topic_dt <= target_end:
                target_topics.append(topic)
                found_in_range = True
                all_before_target = False
            elif topic_dt > target_end:
                # 晚于目标日期，继续翻页
                all_before_target = False
            elif topic_dt < target_start:
                # 早于目标日期，标记已越过
                crossed_date = True
        
        # 如果已经越过目标日期且当前页没有目标日期的帖子，可以停止
        if crossed_date and not found_in_range and all_before_target:
            print(f"[INFO] 已越过目标日期且后续无匹配，停止爬取")
            break
        
        # 检查是否还有更多 - 使用next_end_time判断，因为has_more不可靠
        end_time = result.get("next_end_time")
        if not end_time:
            print(f"[INFO] 已到达最后一页")
            break
    
    # 去重 - 按topic_id去重
    seen_ids = set()
    unique_topics = []
    for topic in target_topics:
        tid = topic.get("topic_id")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique_topics.append(topic)
    
    print(f"[INFO] 爬取完成，共获取 {len(unique_topics)} 条 {target_date} 的帖子")
    return unique_topics


def main():
    parser = argparse.ArgumentParser(description="知识星球按日期爬取工具")
    parser.add_argument("--date", type=str, required=True, help="目标日期 (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=OUTPUT_DIR, help="输出目录")
    parser.add_argument("--group-id", type=str, default=GROUP_ID, help="星球ID")
    parser.add_argument("--multimedia", type=str, default=MULTIMEDIA_DIR, help="附件下载目录 (PDF等文件会下载到此目录)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("知识星球按日期爬取")
    print("=" * 60)
    print(f"目标日期: {args.date}")
    print(f"输出目录: {args.output}")
    print(f"星球ID: {args.group_id}")
    if args.multimedia:
        print(f"附件下载目录: {args.multimedia}")
    print("=" * 60)
    
    # 初始化客户端
    try:
        client = ZsxqApiClient()
    except ZsxqApiError as e:
        print(f"\n[ERROR] 初始化失败: {e}")
        sys.exit(1)
    
    # 获取帖子
    topics = fetch_topics_by_date(client, args.group_id, args.date)
    
    if not topics:
        print(f"\n[WARN] {args.date} 没有获取到任何帖子")
        sys.exit(0)
    
    # 保存帖子
    print(f"\n[INFO] 开始保存 {len(topics)} 条帖子...")
    saved_count = 0
    for topic in topics:
        try:
            topic_data = parse_topic_to_markdown(topic, client, multimedia_dir=args.multimedia)
            file_path = save_topic_to_file(topic_data, args.output)
            print(f"  保存: {file_path.name}")
            if topic_data.get('downloaded_files'):
                print(f"    下载附件: {len(topic_data['downloaded_files'])} 个")
            saved_count += 1
        except Exception as e:
            print(f"  保存失败: {e}")
    
    print(f"\n[SUCCESS] 完成！成功保存 {saved_count}/{len(topics)} 条帖子")
    print(f"输出目录: {args.output}")


if __name__ == "__main__":
    main()
