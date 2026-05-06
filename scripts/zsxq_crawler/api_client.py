#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球API客户端（直接Token版本）
使用Access Token直接调用知识星球API。
"""

import requests
import json
import time
import os
import sys
from datetime import datetime, timezone, timedelta

from config import ZSXQ_ACCESS_TOKEN, BASE_URL, REQUEST_DELAY, MAX_TOPICS_PER_PAGE, GROUP_ID, USER_AGENT


class ZsxqApiError(Exception):
    """知识星球API异常"""
    pass


class ZsxqApiClient:
    """知识星球API客户端（直接Token调用）"""

    def __init__(self, access_token=None):
        """
        初始化客户端

        Args:
            access_token: 访问令牌，默认从config.py读取
        """
        self.access_token = access_token or ZSXQ_ACCESS_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-Key": self.access_token,
        })
        self._check_auth()

    def _check_auth(self):
        """检查认证是否有效"""
        try:
            response = self.session.get(f"{BASE_URL}/groups/{GROUP_ID}")
            if response.status_code == 401:
                raise ZsxqApiError(
                    "Access Token无效或已过期。\n"
                    "请获取新的token或运行: zsxq-cli auth login"
                )
            elif response.status_code != 200:
                # 可能是内部错误，但不一定是认证问题
                print(f"[WARN] API检查返回 HTTP {response.status_code}，继续尝试...")
                return
            
            data = response.json()
            if data.get("succeeded"):
                group = data.get("resp_data", {}).get("group", {})
                print(f"[INFO] 认证成功，星球: {group.get('name', '未知')}")
            else:
                # 可能是内部错误，但不一定是认证问题
                print(f"[WARN] API检查返回错误，继续尝试...")
        except requests.exceptions.RequestException as e:
            raise ZsxqApiError(f"网络请求失败: {e}")

    def get_topics(self, group_id, limit=20, end_time=None, scope="all"):
        """
        获取主题列表（支持分页）

        Args:
            group_id: 星球ID
            limit: 每页数量（1-30）
            end_time: 分页游标（上一页最后一条的create_time）
            scope: 范围 (all/digests/questions)

        Returns:
            dict: {
                "success": bool,
                "topics": list,
                "has_more": bool,
                "next_end_time": str or None,
                "count": int,
            }
        """
        limit = min(max(limit, 1), MAX_TOPICS_PER_PAGE)
        params = {
            "scope": scope,
            "count": str(limit),
        }
        if end_time:
            params["end_time"] = str(end_time)

        try:
            response = self.session.get(
                f"{BASE_URL}/groups/{group_id}/topics",
                params=params,
                timeout=30
            )
            time.sleep(REQUEST_DELAY)

            if response.status_code != 200:
                print(f"[ERROR] API请求失败: HTTP {response.status_code}")
                return {"success": False, "topics": [], "has_more": False, "count": 0}

            data = response.json()
            if not data.get("succeeded"):
                print(f"[ERROR] API返回错误: {data.get('code', 'unknown')}")
                return {"success": False, "topics": [], "has_more": False, "count": 0}

            topics = data.get("resp_data", {}).get("topics", [])
            return {
                "success": True,
                "topics": topics,
                "has_more": data.get("resp_data", {}).get("has_more", False),
                "next_end_time": topics[-1].get("create_time") if topics else None,
                "count": len(topics),
            }
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] 网络请求失败: {e}")
            return {"success": False, "topics": [], "has_more": False, "count": 0}

    def get_topic_detail(self, topic_id):
        """
        获取主题详情

        Args:
            topic_id: 主题ID

        Returns:
            dict: 主题详情，失败返回None
        """
        try:
            response = self.session.get(
                f"{BASE_URL}/topics/{topic_id}",
                timeout=30
            )
            time.sleep(REQUEST_DELAY)

            if response.status_code != 200:
                return None

            data = response.json()
            if data.get("succeeded"):
                return data.get("resp_data", {}).get("topic", {})
            return None
        except requests.exceptions.RequestException:
            return None

    def get_user_info(self):
        """
        获取当前登录用户信息

        Returns:
            dict: 用户信息
        """
        try:
            response = self.session.get(f"{BASE_URL}/self", timeout=30)
            time.sleep(REQUEST_DELAY)

            if response.status_code == 200:
                data = response.json()
                if data.get("succeeded"):
                    return data.get("resp_data", {}).get("user", {})
            return {}
        except requests.exceptions.RequestException:
            return {}


if __name__ == "__main__":
    # 简单测试
    client = ZsxqApiClient()
    print("\n[测试] 获取最近3条主题...")
    result = client.get_topics(GROUP_ID, limit=3)
    print(f"成功: {result['success']}, 条数: {len(result['topics'])}, has_more: {result['has_more']}")
    if result["topics"]:
        tid = result["topics"][0].get("topic_id")
        print(f"\n[测试] 获取主题详情: {tid}")
        detail = client.get_topic_detail(tid)
        print(f"标题: {detail.get('title') if detail else '失败'}")
