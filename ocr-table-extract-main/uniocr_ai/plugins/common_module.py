from enum import Enum
import json
import logging
# from colorlog import ColoredFormatter
import os.path
import ctypes
import gc
from configs import etc_config
from error_message import error_message

def get_logger():
    logger = logging.getLogger()
    if len(logger.handlers) > 0:
        return logger

    logger.setLevel(etc_config['LOG_LEVEL_INFO'])

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(etc_config['LOG_PATH'])
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

logger = get_logger()


# 전체		GC-10	파이선 import	임무상	로그기록
def write_log(message, log_level, oid = ''):
    if log_level == etc_config['LOG_LEVEL_INFO'] or log_level == 'INFO':
        logger.info(oid + ' @ ' + message)
    elif log_level == etc_config['LOG_LEVEL_DEBUG']:
        logger.debug(oid + ' @ ' + message)
    elif log_level == etc_config['LOG_LEVEL_WARNING']:
        logger.warning(oid + ' @ ' + message)
    elif log_level == etc_config['LOG_LEVEL_ERROR'] or log_level == 'ERROR':
        logger.error(oid + ' @ ' + message)

def read_file(filepath):
    try:
        n = os.path.getsize(filepath)
        with open(filepath, 'rb') as file:
            return file.read(n)
    except OSError:
        print(filepath, "파일이 없거나 에러입니다.")
        return None
    
def message(error_code):
    return error_message.get(error_code, '존재하지 않는 에러코드입니다.')


def load_json(file_path):
    '''JSON 파일을 로드하는 함수'''
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)
    

def release_cpu_memory():
    gc.collect()  # Python GC 먼저 수행
    if etc_config['MALLOC_TRIM'] == 'True':
        try:
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except Exception as e:
            print(f"malloc_trim failed: {e}")

class Status(Enum):
    TEXT = -1
    RAW  = 0
    OCR = 1

def page_status(page):
    if page.get_text().strip():
        return Status.TEXT
    return Status.RAW