from common_module import write_log, get_logger
from configs import etc_config
import threading
from werkzeug.sansio.request import Request
from werkzeug.serving import get_interface_ip
import socket
import requests
from datetime import datetime, time as datetime_time, timedelta

# """ LB 기본 설정값 """
lb = None

lb_lock = threading.Lock()

logger = get_logger()

def open_port()->str:
    openport = None
    if etc_config['PORT'] == '':
        if etc_config['CONNECT_TYPE'] == 'HTTPS':
            openport = '443'
        else:
            openport = '80'
    else:
        openport = etc_config['PORT']
    return openport

def time_diff(start, end):
    if isinstance(start, datetime_time): # convert to datetime
        assert isinstance(end, datetime_time)
        start, end = [datetime.combine(datetime.min, t) for t in [start, end]]
    if start <= end: # e.g., 10:33:26-11:15:49
        return end - start
    else: # end < start e.g., 23:55:00-00:25:00
        end += timedelta(1) # +day
        assert end > start
        return end - start


class transaction:
    tid:str = ''
    dt:str = ''
    DATE_FORMAT:str = '%Y-%m-%d %H:%M:%S'
    TIME_OUT_SEC:int = 300
    def __init__(self, tid:str):
        self.tid = tid
        self.dt = datetime.now().strftime(transaction.DATE_FORMAT)

    def __repr__(self):
        return f"<lb.server.transaction tid:{self.tid} dt:{self.dt}>"

    def __str__(self):
        return f"<lb.server.transaction tid:{self.tid} dt:{self.dt}>"

class server:
    ip:str = ''
    transes:list = None

    def __init__(self, ip:str):
        self.ip = ip
        self.transes = list()

    def __repr__(self):
        return f"<lb.server ip:{self.ip} count:{self.transes_size()}>"

    def __str__(self):
        return f"<lb.server ip:{self.ip} count:{self.transes_size()}>"

    def transes_size(self):
        return len(self.transes)

    def remove_timeout(self):
        df = transaction.DATE_FORMAT
        nowDt = datetime.now().strftime(df)
        rmList = list()
        for trans in self.transes:
            s = datetime.strptime(trans.dt, df)
            e = datetime.strptime(nowDt, df)
            dif = time_diff(s, e)
            sec = dif.total_seconds()
            if sec  > transaction.TIME_OUT_SEC:
                rmList.append(trans)
        for trans in rmList:
            self.transes.remove(trans)

    def increase(self, oid:str)->str:
        self.remove_timeout()
        if oid is None:
            return None
        trans = transaction(oid)
        self.transes.append(trans)
        return oid
    def decrease(self, oid:str):
        self.remove_timeout()
        if oid is None:
            return
        for trans in self.transes:
            if trans.tid == oid:
                self.transes.remove(trans)
                break

def get_count(obj:server) -> int:
    return obj.transes_size()

class load_balancer:
    lb_ip:str = ''
    my_ip:str = ''
    ip_list:list = []
    count_lock = threading.Lock()

    def __init__(self, myIp:str):
        lbIp = etc_config['LB_IP']
        if lbIp is None:
            lbIp = ''
        self.lb_ip = lbIp.strip()
        self.my_ip = myIp
        if self.is_lb() == True:
            self.ip_list.append(server(self.lb_ip))
            listStr = etc_config['IP_LIST']
            ipListStr = listStr.split(',')
            for ipStr in ipListStr:
                ipStr = ipStr.strip()
                self.ip_list.append(server(ipStr))

    def is_lb_me(self) -> bool:
        return self.lb_ip == self.my_ip

    def is_lb(self) -> bool:
        return len(self.lb_ip) > 0

    def in_process(self, req:Request)->(str, str):
        if len(self.ip_list) < 1:
            return None, None
        with self.count_lock:
            self.ip_list.sort(key=get_count)
            obj = self.ip_list[0]
            oid = req.headers.get('Hashdata')
            obj.increase(oid)
            print(f'load_balancer.in_process: {self.ip_list}')
        return obj.ip, oid

    def send_request_url(self, ip:str, path:str)->str:
        scheme = etc_config['CONNECT_TYPE']
        port = open_port()
        url = f'{scheme}://{ip}:{port}{path}'
        return url

    def out_process(self, ip:str, oid:str):
        if ip is None or oid is None:
            return
        with self.count_lock:
            for obj in self.ip_list:
                if obj.ip == ip:
                    obj.decrease(oid)
                    break
            print(f'load_balancer.out_process: {self.ip_list}')
    def out_process_request(self, req:Request):
        if len(req.access_route) > 0:
            ipStr = req.access_route[0]
        else:
            ipStr = req.remote_addr
        oid = req.headers.get('oid')
        return self.out_process(ipStr, oid)
    def _send_out_process(self, url:str, headers:dict):
        requests.get(url, headers=headers, verify=False)

    def send_out_process(self, req:Request, path:str):
        oid = req.headers.get('Hashdata')
        if oid is None:
            return
        headers = {'oid': oid}
        scheme = etc_config['CONNECT_TYPE']
        port = open_port()
        url = f'{scheme}://{self.lb_ip}:{port}{path}'
        th = threading.Thread(target=load_balancer._send_out_process, args=(self, url, headers))
        th.start()

def get_lb() -> load_balancer:
    ipStr = get_interface_ip(socket.AF_INET)
    write_log(f"lb.get_lb ip = {ipStr}", etc_config['LOG_LEVEL_INFO'])
    global lb
    global lb_lock
    with lb_lock:
        if lb is not None:
            return lb
        # opt는 한번만 설정하고 계속 사용해야 함.
        # 모델이 변경되는 경우 서버를 내렸다 다시 올려야 함
        if not lb or lb is None:
            try:
                lb = load_balancer(ipStr)
                return lb
            except Exception as e:
                print(f"Exception: {e}")
                return None
    return None

def in_progress(target, req, pth, outPth, redirect, code=307)->object:
    lob = get_lb()
    if lob.is_lb_me() == True:
        ipStr, oid = lob.in_process(req)
        if ipStr is None or oid is None:
            res = target(req, True)
        elif ipStr == lob.lb_ip:
            res = target(req, True)
            lob.out_process(ipStr, oid)
        else:
            url = lob.send_request_url(ipStr, pth)
            res = redirect(url, code=code)
    else:
        res = target(req, True)
        if lob.is_lb() == True:
            lob.send_out_process(req, outPth)
    return res
def out_progress(req)->object:
    lob = get_lb()
    if lob.is_lb() == True:
        lob.out_process_request(req)
    return ''