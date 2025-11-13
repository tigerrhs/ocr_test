import traceback

from common_module import write_log, etc_config
from wf.java_bridge import WFJob, FileEx, JobResult, JFile

def gen_pdf_doc(src_path, pdf_out, uid):
    try:
        job = WFJob()
        job.setJobBatch(True)

        src_file = FileEx(src_path)
        write_log('PDF 변환: ' + src_path, etc_config['LOG_LEVEL_INFO'], uid)
        jr = job.generatePDF(src_file, "temp.pdf", 0)

        if jr.getStatus() == JobResult().JOB_OK:
            jr = job.getJobResult()	
            out_files = jr.getOutFile()  # FileEx[]
            if out_files is None or len(out_files) == 0:
                write_log('변환 실패', etc_config['LOG_LEVEL_ERROR'], uid)
                return True

            out_target = JFile(pdf_out)
            of = out_files[0]
            of.saveToByStream(out_target, True)
            write_log('변환 완료:' + pdf_out, etc_config['LOG_LEVEL_INFO'], uid)
            return False
        else:
            write_log('PDF 변환 실패: ' + str(jr.getErrCode()), etc_config['LOG_LEVEL_INFO'], uid)
            return int(jr.getErrCode())
    except:
        write_log(f"{traceback.format_exc()}", etc_config['LOG_LEVEL_ERROR'], uid)
        return True