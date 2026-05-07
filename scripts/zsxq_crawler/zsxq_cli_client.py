#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球官方 CLI 客户端封装
通过 subprocess 调用 zsxq-cli，自动处理认证和 API 限流。
"""

import subprocess
import json
import time
import os
import sys
import re
import requests

import config
from config import ZSXQ_CLI_PATH, REQUEST_DELAY, MAX_TOPICS_PER_PAGE, USER_AGENT, GROUP_ID


class ZsxqCliError(Exception):
    """zsxq-cli 调用异常"""
    pass


class ZsxqCliClient:
    """zsxq-cli 封装客户端（支持直接Token认证）"""

    def __init__(self, cli_path=None, access_token=None):
        """
        初始化客户端

        Args:
            cli_path: zsxq-cli 可执行文件路径，默认从 config.py 读取
            access_token: 直接提供access token，绕过zsxq-cli
        """
        self.cli_path = cli_path or ZSXQ_CLI_PATH
        self.access_token = access_token or getattr(config, 'ZSXQ_ACCESS_TOKEN', None)
        
        if self.access_token:
            # 使用直接Token认证
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "application/json, application/octet-stream, */*",
                "X-API-Key": self.access_token,
            })
            self._check_token_auth()
        else:
            # 使用zsxq-cli认证
            self._check_cli()

    def _check_cli(self):
        """检查 zsxq-cli 是否可用"""
        if not os.path.exists(self.cli_path):
            # 尝试从 PATH 中查找
            import shutil
            found = shutil.which("zsxq-cli")
            if found:
                self.cli_path = found
            else:
                raise ZsxqCliError(
                    f"zsxq-cli 未找到: {self.cli_path}\n"
                    "请运行: npm install -g zsxq-cli\n"
                    "或修改 config.py 中的 ZSXQ_CLI_PATH"
                )

        # 检查登录状态
        status = self._run("auth", "status", "--json")
        auth_data = status.get("data", {}) if isinstance(status, dict) else {}
        if not auth_data.get("loggedIn"):
            raise ZsxqCliError(
                "zsxq-cli 未登录。请运行: zsxq-cli auth login\n"
                "登录后 token 会自动存储在系统 Keychain 中。"
            )
        user_name = auth_data.get("userName", "未知用户")
        print(f"[INFO] zsxq-cli 已登录: {user_name}")

    def _check_token_auth(self):
        """检查直接Token认证是否有效"""
        try:
            response = self.session.get(f"https://api.zsxq.com/v2/groups/{GROUP_ID}")
            if response.status_code == 401:
                raise ZsxqCliError(
                    "Access Token无效或已过期。\n"
                    "请获取新的token。"
                )
            elif response.status_code != 200:
                # 可能是内部错误，但不一定是认证问题
                print(f"[WARN] API检查返回 HTTP {response.status_code}，继续尝试...")
                return
            
            data = response.json()
            if data.get("succeeded"):
                group = data.get("resp_data", {}).get("group", {})
                print(f"[INFO] Token认证成功，星球: {group.get('name', '未知')}")
            else:
                # 可能是内部错误，但不一定是认证问题
                print(f"[WARN] API检查返回错误，继续尝试...")
        except requests.exceptions.RequestException as e:
            raise ZsxqCliError(f"网络请求失败: {e}")

    def _run(self, *args):
        """
        调用 zsxq-cli 并解析 JSON 输出
        如果使用了直接Token认证，则使用requests调用API
        """
        if self.access_token:
            # 使用直接API调用
            return self._api_call(args)
        
        # 使用zsxq-cli调用
        cmd = [self.cli_path] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            print(f"[ERROR] zsxq-cli 命令超时: {' '.join(args)}")
            return None
        except Exception as e:
            print(f"[ERROR] 调用 zsxq-cli 失败: {e}")
            return None

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                # 尝试解析错误 JSON
                try:
                    err_data = json.loads(stderr)
                    msg = err_data.get("error", {}).get("message", stderr)
                    print(f"[ERROR] zsxq-cli 错误: {msg}")
                except json.JSONDecodeError:
                    print(f"[ERROR] zsxq-cli 错误: {stderr[:500]}")
            return None

        stdout = result.stdout.strip()
        if not stdout:
            return None

        # 尝试解析 JSON（允许控制字符）
        try:
            return json.loads(stdout, strict=False)
        except json.JSONDecodeError:
            # 如果不是 JSON，返回原始字符串
            return stdout

    def _api_call(self, args):
        """
        使用requests直接调用API（Token认证模式）
        解析zsxq-cli命令参数，转换为API调用
        
        Args:
            args: zsxq-cli命令参数元组
            
        Returns:
            dict: API响应
        """
        try:
            # 解析命令参数
            if len(args) >= 2 and args[0] == "group" and args[1] == "+topics":
                # 获取主题列表: group +topics --group-id <id> --limit <n> --json
                group_id = None
                limit = 20
                end_time = None
                
                i = 2
                while i < len(args):
                    if args[i] == "--group-id" and i + 1 < len(args):
                        group_id = args[i + 1]
                        i += 2
                    elif args[i] == "--limit" and i + 1 < len(args):
                        limit = int(args[i + 1])
                        i += 2
                    elif args[i] == "--end-time" and i + 1 < len(args):
                        end_time = args[i + 1]
                        i += 2
                    else:
                        i += 1
                
                return self._get_topics_api(group_id, limit, end_time)
            
            elif len(args) >= 2 and args[0] == "topic" and args[1] == "+detail":
                # 获取主题详情: topic +detail --topic-id <id> --json
                topic_id = None
                i = 2
                while i < len(args):
                    if args[i] == "--topic-id" and i + 1 < len(args):
                        topic_id = args[i + 1]
                        i += 2
                    else:
                        i += 1
                
                return self._get_topic_detail_api(topic_id)
            
            elif len(args) >= 2 and args[0] == "api" and args[1] == "raw":
                # 原始API调用: api raw --method GET --path /v2/...
                method = "GET"
                path = None
                i = 2
                while i < len(args):
                    if args[i] == "--method" and i + 1 < len(args):
                        method = args[i + 1]
                        i += 2
                    elif args[i] == "--path" and i + 1 < len(args):
                        path = args[i + 1]
                        i += 2
                    else:
                        i += 1
                
                return self._api_raw_call(method, path)
            
            elif len(args) >= 1 and args[0] == "user" and "+info" in args:
                # 获取用户信息
                return self._get_user_info_api()
            
            else:
                print(f"[WARN] 未实现的API调用: {args}")
                return None
                
        except Exception as e:
            print(f"[ERROR] API调用异常: {e}")
            return None
    
    def _get_topics_api(self, group_id, limit=20, end_time=None):
        """获取主题列表API"""
        try:
            params = {
                "count": str(limit),
            }
            if end_time:
                # 确保end_time格式正确
                params["end_time"] = str(end_time)
            
            response = self.session.get(
                f"https://api.zsxq.com/v2/groups/{group_id}/topics",
                params=params,
                timeout=30
            )
            time.sleep(REQUEST_DELAY)
            
            if response.status_code != 200:
                print(f"[ERROR] API请求失败: HTTP {response.status_code}")
                return None
            
            data = response.json()
            
            # 转换为zsxq-cli格式
            if data.get("succeeded"):
                topics = data.get("resp_data", {}).get("topics", [])
                # 计算has_more：如果返回了30条，可能还有更多
                has_more = len(topics) >= limit
                return {
                    "success": True,
                    "topics": topics,
                    "has_more": has_more,
                    "next_end_time": topics[-1].get("create_time") if topics else None,
                    "count": len(topics),
                    "rate_limited": False,
                    "rate_limit_msg": "",
                }
            else:
                return {"success": False, "topics": [], "has_more": False, "count": 0, "rate_limited": False, "rate_limit_msg": ""}
        except Exception as e:
            print(f"[ERROR] 获取主题失败: {e}")
            return None
    
    def _api_raw_call(self, method, path):
        """原始API调用"""
        try:
            url = f"https://api.zsxq.com{path}"
            if method.upper() == "GET":
                response = self.session.get(url, timeout=30)
            else:
                response = self.session.post(url, timeout=30)
            
            time.sleep(REQUEST_DELAY)
            
            if response.status_code != 200:
                print(f"[ERROR] API请求失败: HTTP {response.status_code}")
                return None
            
            data = response.json()
            return {"result": {"body": data}}
        except Exception as e:
            print(f"[ERROR] 原始API调用失败: {e}")
            return None
    
    def _get_topic_detail_api(self, topic_id):
        """获取主题详情API"""
        try:
            response = self.session.get(
                f"https://api.zsxq.com/v2/topics/{topic_id}",
                timeout=30
            )
            time.sleep(REQUEST_DELAY)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            if data.get("succeeded"):
                return data.get("resp_data", {}).get("topic", {})
            return None
        except Exception as e:
            print(f"[ERROR] 获取主题详情失败: {e}")
            return None
    
    def _get_user_info_api(self):
        """获取用户信息API"""
        try:
            response = self.session.get(
                "https://api.zsxq.com/v2/self",
                timeout=30
            )
            time.sleep(REQUEST_DELAY)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("succeeded"):
                    return {"success": True, "user": data.get("resp_data", {}).get("user", {})}
            return {}
        except Exception as e:
            print(f"[ERROR] 获取用户信息失败: {e}")
            return {}

    def get_group_info(self, group_id):
        """
        获取星球信息

        Args:
            group_id: 星球ID

        Returns:
            dict: 星球信息，失败返回 None
        """
        data = self._run("api", "raw", "--method", "GET", "--path", f"/v2/groups/{group_id}")
        if data and data.get("result", {}).get("body", {}).get("succeeded"):
            group = data["result"]["body"]["resp_data"]["group"]
            return {
                "id": group.get("id"),
                "name": group.get("name"),
                "description": group.get("description", ""),
                "member_count": group.get("member_count", 0),
                "topic_count": group.get("topic_count", 0),
            }
        return None

    def get_topics(self, group_id, limit=20, end_time=None):
        """
        获取主题列表（支持分页）

        Args:
            group_id: 星球ID
            limit: 每页数量（1-30）
            end_time: 分页游标（上一页最后一条的 create_time）

        Returns:
            dict: {
                "success": bool,
                "topics": list,
                "has_more": bool,
                "next_end_time": str or None,
                "count": int,
                "rate_limited": bool,
                "rate_limit_msg": str,
            }
        """
        return self._run("group", "+topics", "--group-id", str(group_id), "--limit", str(limit), "--json", *("--end-time", str(end_time)) if end_time else ())
    
    def get_topic_detail(self, topic_id):
        """
        获取主题详情（包含完整内容和评论预览）

        Args:
            topic_id: 主题ID

        Returns:
            dict: 主题详情，失败返回 None
        """
        data = self._run("topic", "+detail", "--topic-id", str(topic_id), "--json")
        time.sleep(REQUEST_DELAY)
        if data and data.get("success"):
            return data.get("topic")
        return None
    
    def get_topic_comments(self, topic_id, limit=100):
        """
        获取主题评论列表

        Args:
            topic_id: 主题ID
            limit: 评论数量上限

        Returns:
            list: 评论列表
        """
        data = self._run(
            "api", "call", "get_topic_comments",
            "--params", json.dumps({"topic_id": str(topic_id), "limit": limit}, ensure_ascii=False)
        )
        time.sleep(REQUEST_DELAY)
        if data and data.get("succeeded"):
            return data.get("resp_data", {}).get("comments", [])
        return []
    
    def search_topics(self, group_id, query):
        """
        搜索主题

        Args:
            group_id: 星球ID
            query: 搜索关键词

        Returns:
            list: 主题列表
        """
        data = self._run("topic", "+search", "--group-id", str(group_id), "--query", query, "--json")
        time.sleep(REQUEST_DELAY)
        if data and data.get("succeeded"):
            return data.get("resp_data", {}).get("topics", [])
        return []
    
    def get_user_info(self):
        """
        获取当前登录用户信息

        Returns:
            dict: 用户信息
        """
        data = self._run("user", "+info", "--json")
        time.sleep(REQUEST_DELAY)
        if data and data.get("success"):
            return data.get("user", {})
        return {}
    
    def list_groups(self):
        """
        列出已加入的星球

        Returns:
            list: 星球列表
        """
        data = self._run("group", "+list", "--json")
        time.sleep(REQUEST_DELAY)
        if data and data.get("succeeded"):
            return data.get("resp_data", {}).get("groups", [])
        return []
    
    def download_file(self, file_id, file_name, output_dir):
        """
        下载文件到指定目录
        
        Args:
            file_id: 文件ID
            file_name: 保存的文件名
            output_dir: 输出目录
            
        Returns:
            str: 本地文件路径，失败返回空字符串
        """
        if not file_id or not file_name:
            return ""
        
        try:
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
            
            # 构造下载URL - 知识星球文件使用特殊的CDN链接格式
            # 根据hash构造下载链接
            download_url = f"https://api.zsxq.com/v2/files/{file_id}/download"
            
            # 尝试通过 topics API 获取文件下载链接
            # 知识星球的文件下载通常需要通过特殊的认证URL
            # 使用 zsxq-cli 的 download 命令或构造特殊URL
            
            # 方法1: 尝试直接下载（可能返回重定向）
            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/octet-stream, */*",
                "Referer": "https://wx.zsxq.com/",
            }
            
            # 使用认证session
            if self.access_token:
                # 添加必要的认证头
                auth_headers = {
                    **headers,
                    "X-API-Key": self.access_token,
                }
                response = self.session.get(download_url, headers=auth_headers, timeout=60, stream=True, allow_redirects=True)
            else:
                response = requests.get(download_url, headers=headers, timeout=60, stream=True, allow_redirects=True)
            
            # 如果404，尝试通过 download_url API 获取真实下载链接
            if response.status_code == 404:
                print(f"[INFO] 尝试通过 download_url API 获取下载链接...")
                download_url_api = f"https://api.zsxq.com/v2/files/{file_id}/download_url"
                if self.access_token:
                    resp = self.session.get(download_url_api, headers=auth_headers, timeout=30)
                else:
                    resp = requests.get(download_url_api, headers=headers, timeout=30)
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        if data.get("succeeded") and data.get("resp_data", {}).get("download_url"):
                            download_url = data["resp_data"]["download_url"]
                            print(f"[INFO] 获取到下载链接: {download_url[:100]}...")
                            # 重新下载
                            if self.access_token:
                                response = self.session.get(download_url, headers=headers, timeout=60, stream=True, allow_redirects=True)
                            else:
                                response = requests.get(download_url, headers=headers, timeout=60, stream=True, allow_redirects=True)
                        else:
                            print(f"[WARN] download_url API 返回无效数据")
                    except Exception as e:
                        print(f"[WARN] 解析 download_url API 响应失败: {e}")
                else:
                    print(f"[WARN] download_url API 返回 HTTP {resp.status_code}")
            
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
        获取文件下载URL
        
        Args:
            file_id: 文件ID
            
        Returns:
            str: 下载URL，失败返回None
        """
        try:
            # 使用直接API调用获取文件信息
            if self.access_token:
                response = self.session.get(
                    f"https://api.zsxq.com/v2/files/{file_id}",
                    timeout=30
                )
                time.sleep(REQUEST_DELAY)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("succeeded"):
                        # 构造下载URL
                        download_url = f"https://api.zsxq.com/v2/files/{file_id}/download"
                        return download_url
            
            # 备用：通过CLI获取
            data = self._run("api", "raw", "--method", "GET", "--path", f"/v2/files/{file_id}")
            if data and data.get("result", {}).get("body", {}).get("succeeded"):
                return f"https://api.zsxq.com/v2/files/{file_id}/download"
            
            return None
        except Exception as e:
            print(f"[ERROR] 获取文件下载URL失败: {e}")
            return None


if __name__ == "__main__":
    # 简单测试
    client = ZsxqCliClient()
    print("\n[测试] 获取星球信息...")
    info = client.get_group_info("48888584885518")
    print(json.dumps(info, ensure_ascii=False, indent=2) if info else "失败")

    print("\n[测试] 获取最近3条主题...")
    result = client.get_topics("48888584885518", limit=3)
    print(f"成功: {result['success']}, 条数: {len(result['topics'])}, has_more: {result['has_more']}")
    if result["topics"]:
        tid = result["topics"][0].get("topic_id")
        print(f"\n[测试] 获取主题详情: {tid}")
        detail = client.get_topic_detail(tid)
        print(f"标题: {detail.get('title') if detail else '失败'}")
