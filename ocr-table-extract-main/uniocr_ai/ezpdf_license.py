import base64
import LEA #라이브러리 설치시 uniocr에서 사용하는 부분 참고
from common_module import write_log
from configs import etc_config
import socket
from datetime import datetime

def extract_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        st.connect(('10.255.255.255', 1))
        IP = st.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        st.close()
    return IP

key = bytes([0x61, 0x64, 0x73, 0x74, 0x61, 0x72, 0x2E, 0xB9, 0xAB, 0xBC, 0xB1, 0xB1, 0xA4, 0xB0, 0xED, 0xB0,
             0xFC, 0xB8, 0xAE, 0xBD, 0xC3, 0xBD, 0xBA, 0xC5, 0xDB, 0xBE, 0xCF, 0xC8, 0xA3, 0xC5, 0xB0, 0x2E])
iv = bytes([0x27, 0x28, 0x27, 0x6d, 0x2d, 0xd5, 0x4e, 0x29, 0x2c, 0x56, 0xf4, 0x2a, 0x65, 0x2a, 0xae, 0x08])

def licenseCheck(licensePath:str, productType:str)->bool:
    with open(licensePath, 'rb') as file:
        enc_data_64 = file.read()
        enc_data = base64.b64decode(enc_data_64)
        leaCBC = LEA.CBC(False, key, iv)
        dec_str = leaCBC.update(enc_data).decode('utf-8')
        info = dec_str.split('|')
        today = datetime.now()

    if productType != info[0]:
        write_log(f'Product Type error:{productType}', etc_config['LOG_LEVEL_ERROR'])
        return False
    
    local_ip = extract_ip()
    ip_list = info[1].split(',')
    has_ip = False
    for ip in ip_list:
        if local_ip == ip.strip():
            has_ip = True
            break
        if ip.strip() == '*':
            has_ip = True
            break
    if has_ip == False:
        write_log(f'IP Address error: {local_ip}', etc_config['LOG_LEVEL_ERROR'])
        return False
    
    start = datetime.strptime(info[2], "%Y-%m-%d")
    if today < start or start is None:
        write_log(f'License has expired: {today}', etc_config['LOG_LEVEL_ERROR'])
        return False

    end = datetime.strptime(info[3][:10], "%Y-%m-%d")
    if today > end or end is None:
        write_log(f'License has expired: {today}', etc_config['LOG_LEVEL_ERROR'])
        return False
    
    return True

def create_lience():
    original_text = '100|192.168.1.118,192.168.196.97,192.168.1.73,192.168.1.219,192.168.196.33,192.168.1.22,192.168.196.183,172.28.207.131|2022-06-30|2023-02-28'

    leaCBC = LEA.CBC(True, key, iv, True)
    enc_data = leaCBC.update(original_text) + leaCBC.final()
    encoded64 = base64.b64encode(enc_data)
    print('encoded64:\t', encoded64)
    decoded64 = base64.b64decode(encoded64)
    print('decoded64:\t', decoded64)
    leaCBC = LEA.CBC(False, key, iv, True)
    dec_data = leaCBC.update(decoded64)
    print('dec_data size:\t', len(dec_data))
    dec_data += leaCBC.final()
    print('dec_data size:\t', len(dec_data))
    print('dec_data:\t', dec_data)
    print('dec_data_last:\t', key[-1])

if __name__ == '__main__' :
    create_lience()
    check = licenseCheck('./lice/licenseFile.dat', '100')

    print(f'check:{check}')