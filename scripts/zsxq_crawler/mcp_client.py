#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球MCP API客户端 (SSE版本)
使用API Key直接调用知识星球MCP服务，支持SSE流式响应。
"""

import requests
import json
import time
import uuid
import re
from datetime import datetime, timezone, timedelta

from config import GROUP_ID, REQUEST_DELAY, MAX_TOPICS_PER_PAGE, MAX_PAGES


class ZsxqMcpClient:
    """知识星球MCP客户端 (SSE版本)"""

    def __init__(self, api_key):
        """
        初始化MCP客户端

        Args:
            api_key: MCP API Key
        """
        self.api_key = api_key
        self.base_url = "https://mcp.zsxq.com"

    def _call(self, method, params=None):
        """
        调用MCP工具 (SSE格式)

        Args:
            method: 方法名
            params: 参数

        Returns:
            dict: 响应结果
        """
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {}
        }

        try:
            response = requests.post(
                f"{self.base_url}/topic/mcp?api_key={self.api_key}",
                json=payload,
                headers={
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                },
                timeout=60,
                stream=True
            )

            if response.status_code != 200:
                print(f"[ERROR] MCP请求失败: HTTP {response.status_code}")
                return None

            # 解析SSE响应
            result = None
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "result" in data:
                            result = data["result"]
                        elif "error" in data:
                            print(f"[ERROR] MCP错误: {data['error']}")
                            return None
                    except json.JSONDecodeError:
                        continue

            return result
        except Exception as e:
            print(f"[ERROR] MCP调用异常: {e}")
            return None

    def list_groups(self):
        """列出已加入的星球"""
        return self._call("list_groups")

    def get_group_topics(self, group_id, limit=20, end_time=None):
        """
        获取星球主题列表

        Args:
            group_id: 星球ID
            limit: 每页数量
            end_time: 分页游标

        Returns:
            dict: 主题列表结果
        """
        params = {
            "group_id": str(group_id),
            "limit": min(max(limit, 1), MAX_TOPICS_PER_PAGE)
        }
        if end_time:
            params["end_time"] = str(end_time)

        return self._call("get_group_topics", params)

    def get_topic_detail(self, topic_id):
        """
        获取主题详情

        Args:
            topic_id: 主题ID

        Returns:
            dict: 主题详情
        """
        return self._call("get_topic_detail", {"topic_id": str(topic_id)})

    def search_topics(self, group_id, query):
        """
        搜索主题

        Args:
            group_id: 星球ID
            query: 搜索关键词

        Returns:
            list: 搜索结果
        """
        result = self._call("search_topics", {
            "group_id": str(group_id),
            "query": query
        })
        return result or []


def test_connection():
    """测试MCP连接"""
    client = ZsxqMcpClient("6a16530e00ba3f4069476c6301460b1c")

    print("[测试] 列出星球...")
    groups = client.list_groups()
    if groups:
        print(f"✅ 成功！加入 {len(groups)} 个星球")
        for g in groups[:3]:
            print(f"  - {g.get('name', '未知')} (ID: {g.get('id', 'N/A')})")
    else:
        print("❌ 失败，无法获取星球列表")

    return client


if __name__ == "__main__":
    test_connection()
