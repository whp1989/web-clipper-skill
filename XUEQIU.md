# 雪球股票信息获取 (camofox-browser版)

## 功能

获取雪球网指定股票的讨论帖子，使用 camofox-browser 绕过 WAF。

## 前置要求

1. **camofox-browser 服务** 必须正在运行
2. **Xvfb** 虚拟显示已启动

### 启动 camofox 服务

```bash
# 1. 启动 Xvfb
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset > /dev/null 2>&1 &

# 2. 设置环境变量
export DISPLAY=:99

# 3. 启动 camofox 服务
cd /tmp/camofox-browser
CAMOFOX_PORT=9377 DISPLAY=:99 node server.js > /tmp/camofox.log 2>&1 &
```

### 关键配置修改

需要修改 camofox-js 的 VirtualDisplay 类，优先使用环境变量 DISPLAY：

编辑文件：`/tmp/camofox-browser/node_modules/camoufox-js/dist/virtdisplay.js`

```javascript
get display() {
    if (this._display === null) {
        // 优先使用环境变量 DISPLAY
        const envDisplay = process.env.DISPLAY;
        if (envDisplay) {
            const match = envDisplay.match(/:(\d+)/);
            if (match) {
                this._display = parseInt(match[1], 10);
                return this._display;
            }
        }
        this._display = VirtualDisplay._free_display();
    }
    return this._display;
}
```

## 使用方法

### 基本用法

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_camofox.py \
  --symbol "SH688008" \
  --name "澜起科技"
```

### 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--symbol` | 是 | 股票代码，如 SH688008 |
| `--name` | 是 | 股票名称，如 澜起科技 |
| `--count` | 否 | 获取讨论数量（默认20） |
| `--output` | 否 | 输出目录（默认 syncthing/raw） |

### 输出示例

```
============================================================
雪球股票讨论获取 (camofox版)
============================================================
股票代码: SH688008
股票名称: 澜起科技
输出目录: /root/.openclaw/workspace/syncthing/raw
[INFO] 获取 澜起科技(SH688008) 的讨论...
[INFO] Tab created: f68e00ce-0bef-4d0d-a0e5-38f41e193e34
[INFO] 快照获取成功
[INFO] 解析到 10 条讨论
✅ 已保存: syncthing/raw/2026-05-10_澜起科技_SH688008_雪球讨论.md
✅ NAS同步已触发
```

## 输出文件格式

保存为 Markdown 文件：`YYYY-MM-DD_股票名称_股票代码_雪球讨论.md`

```markdown
---
title: 澜起科技(SH688008) - 雪球讨论
date: 2026-05-10
source: xueqiu.com
symbol: SH688008
---

# 澜起科技(SH688008) - 雪球讨论

**获取时间**: 2026-05-10 21:56:20
**数据来源**: [雪球网](https://xueqiu.com/S/SH688008)
**讨论数量**: 10条

---

### 1. 平凡如我1988
**时间**: 4分钟前· 来自iPhone | **点赞**: 2

CXL内存扩展技术在AI数据中心的核心价值...

---
```

## 技术说明

### 为什么使用 camofox-browser？

1. **WAF 拦截**：雪球网有阿里云 WAF 保护，直接 API 请求会被拦截
2. **反爬机制**：需要真实浏览器环境才能绕过检测
3. **动态内容**：雪球是 SPA 应用，需要 JavaScript 渲染

### camofox 优势

- 基于 Firefox 的反检测浏览器
- 自动处理指纹和特征伪装
- 支持页面交互（滚动、点击等）
- 提供 HTTP API 接口，易于集成

## 故障排查

### 问题1：camofox 服务无法启动

**现象**：浏览器启动失败，显示 "cannot open display"

**解决**：
1. 确保 Xvfb 已启动：`ps aux | grep Xvfb`
2. 确保 DISPLAY 环境变量已设置：`echo $DISPLAY`
3. 修改 virtdisplay.js 使用环境变量 DISPLAY

### 问题2：页面内容为空

**现象**：快照获取成功但内容为空

**解决**：
1. 增加等待时间：`time.sleep(15)`
2. 多次滚动触发懒加载
3. 检查是否需要登录（部分股票需要）

### 问题3：获取的讨论数量少

**现象**：只获取到少量讨论

**解决**：
1. 增加滚动次数和滚动距离
2. 等待更长时间让页面加载
3. 检查是否需要点击"加载更多"

## 注意事项

1. **camofox 服务需要保持运行**，预热后才能快速响应
2. **部分股票需要登录**才能查看讨论
3. **雪球页面是 SPA**，需要等待 JavaScript 渲染
4. **频繁请求可能触发限制**，建议控制请求频率

## 更新日志

### 2026-05-10
- 初始版本，使用 camofox-browser 绕过 WAF
- 支持获取股票讨论并保存为 Markdown
- 集成 NAS 同步和 Gotify 通知
