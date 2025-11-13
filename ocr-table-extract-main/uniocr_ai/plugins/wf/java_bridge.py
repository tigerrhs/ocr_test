import os
from threading import Lock
import jpype
from jpype import JClass

from common_module import logger

def init_jvm():
    if not jpype.isJVMStarted():
        BASE = os.path.dirname(__file__)
        class_path = os.path.join(BASE, "Lib", "WF3JavaClient-3.1.35_jdk1.5.jar")
        res_dir = os.path.join(BASE, "conf")
        jpype.startJVM(
            classpath=[class_path, res_dir],
            convertStrings=True,
            jvmpath=None
        )
    bind_java_classes()

_java = {}
_bound = False
_lock = Lock()

def bind_java_classes():
    global _bound, JobResult
    if _bound:
        return True
    
    with _lock:
        _WFJob = JClass("com.unidocs.workflow.client.WFJob")
        _FileEx = JClass("com.unidocs.workflow.common.FileEx")
        JobResult = JClass("com.unidocs.workflow.common.JobResult")
        _JFile = JClass("java.io.File")
        _java['WFJob']  = _WFJob
        _java['FileEx'] = _FileEx
        _java['Result'] = JobResult
        _java['JFile']  = _JFile
        _bound = True


def WFJob():
    return _java['WFJob']()

def FileEx(path):
    return _java['FileEx'](path)

def JobResult():
    return _java['Result']

def JFile(path):
    return _java['JFile'](path)


def jvm_hooks(app):
    @app.before_request
    def _attach_jvm_thread():
        if jpype.isJVMStarted() and not jpype.isThreadAttachedToJVM():
            jpype.attachThreadToJVM()

    @app.teardown_request
    def _detach_jvm_thread(exc):
        if jpype.isJVMStarted() and jpype.isThreadAttachedToJVM():
            jpype.detachThreadFromJVM()


def register(app):
    """플러그인 엔트리포인트"""
    try:
        init_jvm()
    except Exception as e:
        logger.critical("Jpype JVM 실행 오류: " + str(e))
        return

    jvm_hooks(app)


if __name__ == "__main__":
    import traceback
    try:
        init_jvm()
    except:
        traceback.print_exc()

    job = WFJob()
    job.setJobBatch(True)