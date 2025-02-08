import json
import logging
import os
from datetime import datetime

import xiaomi_cloud
import config

# 基础配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

_LOGGER = logging.getLogger(__name__)

def save_device_list():
    try:
        # 读取配置
        conf = config.from_file()
        
        # 登录米家账号
        cloud = xiaomi_cloud.MiotCloud(username=conf.username, password=conf.password)
        cloud.login()
        _LOGGER.info('登录米家账号成功')

        # 获取米家设备列表
        device_list = cloud.get_device_list()
        _LOGGER.info('共获取到%d个设备', len(device_list))

        # 按设备类型分类
        devices_by_type = {}
        for device in device_list:
            model = device['model']
            if model not in devices_by_type:
                devices_by_type[model] = []
            devices_by_type[model].append({
                'name': device['name'],
                'model': device['model'],
                'did': device['did'],
                'token': device.get('token', ''),
                'ip': device.get('localip', ''),
                'mac': device.get('mac', ''),
                'parent_id': device.get('parent_id', ''),
                'parent_model': device.get('parent_model', ''),
            })

        # 生成输出文件名，包含时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'devices_{timestamp}.json'

        # 保存设备信息
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_count': len(device_list),
                'timestamp': datetime.now().isoformat(),
                'devices_by_type': devices_by_type,
                'all_devices': device_list,  # 保存完整的设备信息
            }, f, ensure_ascii=False, indent=2)

        _LOGGER.info('设备信息已保存到文件: %s', output_file)
        
        # 打印设备类型统计
        _LOGGER.info('\n设备类型统计:')
        for model, devices in devices_by_type.items():
            _LOGGER.info('%s: %d个设备', model, len(devices))
            # 打印该类型下的所有设备名称
            for device in devices:
                _LOGGER.info('  - %s', device['name'])

    except Exception as e:
        _LOGGER.error('获取设备列表失败: %s', e)

if __name__ == '__main__':
    save_device_list() 