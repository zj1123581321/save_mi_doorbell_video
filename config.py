import json
from typing import NamedTuple


class Config(NamedTuple):
    username: str
    password: str
    save_path: str
    schedule_minutes: int
    ffmpeg: str
    merge: bool
    door_name: str
    wechat_webhook: str


def from_file(path='config.json') -> Config:
    with open(path, 'r',encoding='utf-8') as f:
        config = json.load(f)
        return Config(**config)
