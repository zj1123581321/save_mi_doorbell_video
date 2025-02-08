import sys

import xiaomi_cloud
from doorbell import MiDoorbell
import config
import schedule
import time
import json
import os
import logging
import requests

class WeChatWebhookHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.webhook_url = conf.wechat_webhook
        
    def emit(self, record):
        # 仅处理ERROR级别日志
        if record.levelno >= logging.ERROR:
            try:
                # 格式化日志消息
                msg = self.format(record)
                
                # 构造企业微信消息
                data = {
                    "msgtype": "text",
                    "text": {
                        "content": f"[ERROR]门铃存档机器人\n{msg}"
                    }
                }
                
                # 发送webhook请求
                response = requests.post(
                    self.webhook_url,
                    json=data,
                    timeout=5
                )
                response.raise_for_status()
                
            except Exception as e:
                # 发送失败不影响原有日志记录
                print(f"Failed to send WeChat notification: {str(e)}")

# 基础配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 获取logger
_LOGGER = logging.getLogger(__name__)

conf = config.from_file()

# 添加企业微信webhook handler
wechat_handler = WeChatWebhookHandler()
wechat_handler.setLevel(logging.ERROR)  # 只处理ERROR级别
_LOGGER.addHandler(wechat_handler)


def check_and_download():
    try:
        # 登录米家账号
        cloud = xiaomi_cloud.MiotCloud(username=conf.username, password=conf.password)
        cloud.login()
        _LOGGER.info('登录米家账号成功')

        # 获取米家设备列表
        device_list = cloud.get_device_list()
        _LOGGER.info('共获取到%d个设备', len(device_list))

        # 读取已经处理过的视频，避免重复处理
        data = {}
        data_path = './data.json'
        if os.path.exists(data_path):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                _LOGGER.info('成功读取历史记录文件')
            except UnicodeDecodeError:
                # 如果UTF-8解码失败，尝试使用其他编码读取并重新保存为UTF-8
                _LOGGER.warning('历史记录文件编码错误，尝试修复...')
                try:
                    with open(data_path, 'r', encoding='gbk') as f:
                        data = json.load(f)
                    # 立即以UTF-8重新保存
                    with open(data_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    _LOGGER.info('历史记录文件已修复并重新保存为UTF-8编码')
                except Exception as e:
                    _LOGGER.error('修复历史记录文件失败: %s', e)
                    data = {}
            except Exception as e:
                _LOGGER.error('读取历史记录文件失败: %s', e)
                data = {}

        _LOGGER.info('配置的门铃列表: %s', conf.door_names)
        
        # 初始化每个门铃的历史记录
        for door_name in conf.door_names:
            if not isinstance(door_name, str):
                _LOGGER.error('门铃名称必须是字符串类型，当前类型: %s, 值: %s', type(door_name), door_name)
                continue
                
            if door_name not in data:
                data[door_name] = {}
                _LOGGER.info('为门铃 %s 初始化历史记录', door_name)

        # 匹配多个智能门铃设备
        for door_name in conf.door_names:
            if not isinstance(door_name, str):
                continue
                
            _LOGGER.info('正在自动匹配智能门铃设备...，门铃设备名称为：%s', door_name)
            device = None
            for d in device_list:
                if d['model'].startswith('madv.cateye.') and d['name'] == door_name:
                    device = d
                    break

            if not device:
                _LOGGER.error('未找到名为 %s 的米家智能门铃', door_name)
                continue

            cam = MiDoorbell(cloud, device['name'], device['did'], device['model'])
            _LOGGER.info('匹配门铃设备成功，设备名称为:%s(%s)', cam.name, cam.model)

            # 获取门铃事件列表(过滤历史已处理)
            event_list = [event for event in cam.get_event_list() 
                         if event.fileId not in data[door_name]]
            _LOGGER.info('门铃 %s 本次共获取到%d条门铃事件', door_name, len(event_list))

            # 处理并下载视频
            for event in event_list:
                data[door_name][event.fileId] = event._asdict()

                _LOGGER.info(event.event_desc() + ',视频下载中...')
                
                # 保存视频到指定文件
                path = cam.download_video(event, conf.save_path, conf.merge, conf.ffmpeg)
                _LOGGER.info('视频已保存到：%s', path)

        # 存储已经处理过的记录
        try:
            with open(data_path, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
            _LOGGER.info('历史记录已保存')
        except Exception as e:
            _LOGGER.error('保存历史记录失败: %s', e)

        # 计算总处理数量
        total_events = sum(len(door_data) for door_data in data.values())
        _LOGGER.info('本次共处理完成, 历史总处理%d条门铃事件', total_events)

    except Exception as e:
        _LOGGER.error('出错了:%s', e)

    return ''


if __name__ == '__main__':
    # # 普通info日志,不会发送企业微信通知
    # _LOGGER.info("This is an info message")

    # # error日志会同时记录日志并发送企业微信通知
    # _LOGGER.error("This is an error message")


    # 检查并下载视频
    check_and_download()

    # 定时执行
    schedule.every(conf.schedule_minutes).minutes.do(check_and_download)

    while True:
        schedule.run_pending()
        time.sleep(1)
