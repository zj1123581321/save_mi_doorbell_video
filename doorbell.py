from urllib.parse import urlencode
import logging
import time
from datetime import datetime
import locale
import binascii
import os

import requests
import subprocess
from Crypto.Cipher import AES
from typing import NamedTuple, List

_LOGGER = logging.getLogger(__name__)


class DoorbellEvent(NamedTuple):
    eventTime: int
    fileId: str
    eventType: str

    def date_time_fmt(self):
        t = datetime.fromtimestamp(float(self.eventTime) / 1000)
        return t.strftime('%Y-%m-%d %H:%M:%S')

    def short_time_fmt(self):
        t = datetime.fromtimestamp(float(self.eventTime) / 1000)
        return t.strftime('%H%M%S')

    def shot_date_fmt(self):
        t = datetime.fromtimestamp(float(self.eventTime) / 1000)
        return t.strftime('%Y%m%d')

    def event_type_name(self):
        if self.eventType == 'Pass':
            return '有人在门前经过'
        elif self.eventType == 'Pass:Stay':
            return '有人在门停留'
        elif self.eventType == 'Bell':
            return '有人按门铃'
        elif self.eventType == 'Pass:Bell':
            return '有人按门铃'
        else:
            return self.eventType

    def event_desc(self):
        return '%s %s' % (self.date_time_fmt(), self.event_type_name())


class MiDoorbell:

    def __init__(self, xiaomi_cloud, name, did, model):
        self.xiaomi_cloud = xiaomi_cloud
        self.name = name
        self._state_attrs = {}
        self.miot_did = did
        self.model = model

    def get_event_list(self, start_time=None, end_time=None, limit=10) -> List[DoorbellEvent]:
        mic = self.xiaomi_cloud
        lag = locale.getlocale()[0]
        if start_time:
            stm = start_time
        else:
            stm = int(time.time() - 86400 * 1) * 1000

        if end_time:
            etm = end_time
        else:
            etm = int(time.time() * 1000 + 999)

        api = mic.get_api_by_host('business.smartcamera.api.io.mi.com', 'common/app/get/eventlist')
        rqd = {
            'did': self.miot_did,
            'model': self.model,
            'doorBell': True,
            'eventType': 'Default',
            'needMerge': True,
            'sortType': 'DESC',
            'region': str(mic.default_server).upper(),
            'language': lag,
            'beginTime': stm,
            'endTime': etm,
            'limit': limit,
        }

        all_list = []
        is_continue = True
        next_time = etm

        while is_continue:
            rqd['endTime'] = next_time

            rdt = mic.request_miot_api(api, rqd, method='GET', crypt=True) or {}
            data = rdt.get('data', {})
            is_continue = data['isContinue']
            next_time = data['nextTime']

            rls = data.get('thirdPartPlayUnits') or []

            for item in rls:
                all_list.append(DoorbellEvent(
                    eventTime=int(item['createTime']),
                    fileId=item['fileId'],
                    eventType=item['eventType']))

        return all_list

    def download_video(self, event: DoorbellEvent, save_path, merge=False, ffmpeg=None):
        m3u8_url = self.get_video_m3u8_url(event)
        resp = requests.get(m3u8_url)
        lines = resp.content.splitlines()
        video_cnt = 0
        key = None
        iv = None

        # 新的路径结构：门铃名称/年月/日期/时间
        t = datetime.fromtimestamp(float(event.eventTime) / 1000)
        year_month = t.strftime('%Y%m')
        day = t.strftime('%y%m%d')
        
        # 构建完整的视频保存路径
        video_dir = os.path.abspath(f"{save_path}/{self.name}/{year_month}/{day}")
        video_name = f"{event.short_time_fmt()}.mp4"
        video_path = os.path.join(video_dir, video_name)
        ts_path = os.path.join(video_dir, "ts")
        
        # 确保所有必要的目录都存在
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(ts_path, exist_ok=True)

        _LOGGER.debug('视频目录: %s', video_dir)
        _LOGGER.debug('TS目录: %s', ts_path)
        _LOGGER.debug('最终视频路径: %s', video_path)

        # 保存文件的同时，生成文件清单到filelist
        with open(os.path.join(ts_path, 'filelist'), 'w', encoding='utf-8') as filelist:
            for line in lines:
                line = line.decode('utf-8')
                # 解析密钥信息
                if line.startswith('#EXT-X-KEY'):
                    start = line.index('URI="')
                    url = line[start: line.index('"', start + 10)][5:]
                    key = requests.get(url).content
                    iv = binascii.unhexlify(line[line.index('IV='):][5:])

                # 解析视频URL并下载
                if line.startswith('http'):
                    r = requests.get(line)
                    video_cnt += 1
                    crypto = AES.new(key, AES.MODE_CBC, iv)
                    filename = str(video_cnt) + '.ts'

                    with open(os.path.join(ts_path, filename), 'wb') as f:
                        f.write(crypto.decrypt(r.content))

                    # 添加文件名到列表中，方便ffmpeg做视频合并
                    filelist.writelines('file \'' + filename + '\'\n')

        if video_cnt > 0 and merge and ffmpeg:
            # 使用ffmpeg进行文件合并
            try:
                # 生成相对路径的filelist文件
                filelist_path = os.path.join(ts_path, 'filelist')
                with open(filelist_path, 'w', encoding='utf-8') as f:
                    for i in range(1, video_cnt + 1):
                        f.write(f"file '{i}.ts'\n")

                # 使用绝对路径
                cmd = [
                    ffmpeg,
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', filelist_path,
                    '-y',
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    video_path
                ]
                _LOGGER.debug('执行ffmpeg命令: %s', ' '.join(cmd))
                
                # 设置环境变量以处理不同操作系统的编码
                env = os.environ.copy()
                if os.name == 'nt':  # Windows 环境
                    env['PYTHONIOENCODING'] = 'utf-8'
                    # 将命令列表转换为字符串，避免Windows的命令行参数解析问题
                    cmd_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd)
                    result = subprocess.run(
                        cmd_str,
                        cwd=ts_path,
                        env=env,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        encoding='utf-8',
                        errors='replace'
                    )
                else:  # Linux/Docker 环境
                    result = subprocess.run(
                        cmd,
                        cwd=ts_path,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        encoding='utf-8',
                        errors='replace'
                    )

                if result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode, 
                        cmd,
                        output=result.stdout,
                        stderr=result.stderr
                    )

                _LOGGER.debug('ffmpeg输出: %s', result.stdout)
                
                # 检查输出文件是否存在且大小大于0
                if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                    # 合并成功后删除ts文件夹
                    import shutil
                    shutil.rmtree(ts_path)
                    _LOGGER.info('视频合并成功：%s', video_path)
                    return video_dir
                else:
                    raise Exception('视频文件创建失败或大小为0')

            except Exception as e:
                _LOGGER.error('视频合并失败: %s', e)
                if hasattr(e, 'stderr'):
                    _LOGGER.error('ffmpeg错误输出: %s', e.stderr)
                # 合并失败时保留ts文件夹
                return ts_path

        return video_dir

    def get_video_m3u8_url(self, event: DoorbellEvent):
        mic = self.xiaomi_cloud
        fid = event.fileId
        pms = {
            'did': str(self.miot_did),
            'model': self.model,
            'fileId': fid,
            'isAlarm': True,
            'videoCodec': 'H265',
        }
        api = mic.get_api_by_host('business.smartcamera.api.io.mi.com', 'common/app/m3u8')
        pms = mic.rc4_params('GET', api, {'data': mic.json_encode(pms)})
        pms['yetAnotherServiceToken'] = mic.service_token
        url = f'{api}?{urlencode(pms)}'
        return url
