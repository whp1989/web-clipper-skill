#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球API直接调用（使用access_token）
尝试各种认证方式调用知识星球API。
"""

import requests
import json
import time
from datetime import datetime, timezone, timedelta

# 测试各种认证方式
ACCESS_TOKEN = "6a16530e00ba3f4069476c6301460b1c"
GROUP_ID = "48888584885518"


def test_auth_methods():
    """测试各种认证方式"""
    methods = [
        # 方法1: Bearer Token
        {
            "name": "Bearer Token",
            "headers": {
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        },
        # 方法2: Query Parameter
        {
            "name": "Query Parameter",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "params": {"access_token": ACCESS_TOKEN}
        },
        # 方法3: Cookie
        {
            "name": "Cookie",
            "headers": {
                "Cookie": f"zsxq_access_token={ACCESS_TOKEN}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        },
        # 方法4: X-API-Key
        {
            "name": "X-API-Key",
            "headers": {
                "X-API-Key": ACCESS_TOKEN,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        },
        # 方法5: zsxq-cli格式
        {
            "name": "zsxq-cli格式",
            "headers": {
                "Authorization": ACCESS_TOKEN,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        },
    ]

    url = f"https://api.zsxq.com/v2/groups/{GROUP_ID}"

    for method in methods:
        print(f"\n[测试] {method['name']}...")
        try:
            response = requests.get(
                url,
                headers=method.get("headers", {}),
                params=method.get("params", {}),
                timeout=15
            )
            print(f"  HTTP状态: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get("succeeded"):
                    group = data.get("resp_data", {}).get("group", {})
                    print(f"  ✅ 成功！星球: {group.get('name', '未知')}")
                    return method
                else:
                    print(f"  ⚠️ API返回错误: {data}")
            else:
                print(f"  ❌ 失败: {response.text[:200]}")

        except Exception as e:
            print(f"  ❌ 异常: {e}")

        time.sleep(1)

    return None


if __name__ == "__main__":
    print("=" * 60)
    print("测试知识星球API认证方式")
    print("=" * 60)

    working_method = test_auth_methods()

    if working_method:
        print(f"\n✅ 找到有效认证方式: {working_method['name']}")
    else:
        print("\n❌ 所有认证方式均失败")
        print("建议: 使用zsxq-cli auth login完成OAuth授权")
