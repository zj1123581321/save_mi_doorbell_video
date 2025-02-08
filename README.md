# 米家智能门铃视频存档工具

小米智能门铃的视频，在不开VIP的情况下，只能实现3天滚动存储。如果要实现更长周期的存储，费用并不便宜。
本程序通过登录米家账号，可定时将门铃的视频存到指定位置，如果存储空间足够，可以实现无限期视频存储。


## 功能特性

- 自动下载米家智能门铃事件视频
- 支持多门铃设备同时监控（可视门铃广州、智能门铃大连湾等）
- TS视频分片自动合并为 MP4 格式
- 企业微信异常通知功能
- 历史记录自动修复机制
- 支持 Docker 容器化部署
- 设备列表自动发现工具

## 快速开始

### 配置文件准备

复制示例配置文件并修改 `config.json`：

```bash
cp config.example.json config.json
```

```json
{
  "username": "您的米家账号",
  "password": "您的密码",
  "save_path": "./video",
  "ffmpeg": "/path/to/ffmpeg",
  "schedule_minutes": 60,
  "merge": true,
  "door_names": ["门铃设备1", "门铃设备2"],
  "wechat_webhook": "企业微信机器人Webhook地址"
}
```

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 列出可用设备（帮助确认door_names）
python list_devices.py

# 启动主程序
python main.py
```

### Docker 运行

```bash
# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

## 高级配置

### 视频合并功能

- 需要正确配置 ffmpeg 路径
- 合并失败时会保留原始 TS 文件
- Windows 环境自动处理路径空格问题

### 错误通知机制

当发生 `ERROR` 级别错误时，会通过企业微信机器人发送通知。相关代码片段：

```python
# python:main.py (示例，实际代码位置可能不同)
# startLine: 13
# endLine: 43
# ... (省略部分代码)
import logging

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 示例错误处理
try:
    # 模拟一个可能出错的操作
    result = 1 / 0
except Exception as e:
    logger.error(f"发生错误: {e}")
    # 在这里添加企业微信通知逻辑
    # send_wechat_notification(f"发生错误: {e}") # 假设有这样一个函数
    pass

# ... (省略部分代码)
```

### 数据持久化

建议挂载以下目录：

- `/app/config.json` 配置文件
- `/app/data.json` 下载记录
- `/app/video` 视频存储目录

## 高级用法

### 设备发现工具

```bash
python list_devices.py
```

生成包含设备详细信息的 JSON 文件（含设备 DID、型号、所属房间等信息）。

### 历史记录修复

当 `data.json` 编码错误时，程序会自动尝试：

1. 用 GBK 编码读取
2. 转换为 UTF-8 保存
3. 继续正常运行

## 目录结构

```
.
├── config.example.json  # 配置示例文件
├── config.json          # 用户配置文件
├── data.json            # 下载记录数据库
├── docker-compose.yml   # Docker 编排文件
├── requirements.txt     # Python 依赖
└── video/                # 视频存储目录
    └── 门铃名称/
        └── 年月/
            └── 日期/
                └── 时间.mp4
```

## 注意事项

1. 首次运行建议先执行 `list_devices.py` 确认门铃名称。
2. Docker 版需要正确挂载视频存储目录。
3. 企业微信通知需配置正确的 Webhook 地址。
4. Windows 环境请使用 Powershell 执行脚本。