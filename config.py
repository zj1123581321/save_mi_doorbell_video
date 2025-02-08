import json
from typing import NamedTuple, List


class Config(NamedTuple):
    username: str
    password: str
    save_path: str
    schedule_minutes: int
    ffmpeg: str
    merge: bool
    door_names: List[str]
    wechat_webhook: str


def from_file(path='config.json') -> Config:
    with open(path, 'r',encoding='utf-8') as f:
        config = json.load(f)
        
        # 兼容处理：如果配置文件中使用的是旧的 door_name
        if 'door_name' in config:
            # 如果 door_name 已经是列表，直接使用
            if isinstance(config['door_name'], list):
                config['door_names'] = config.pop('door_name')
            # 如果 door_name 是字符串，转换为列表
            else:
                config['door_names'] = [config.pop('door_name')]
            
        return Config(**config)
