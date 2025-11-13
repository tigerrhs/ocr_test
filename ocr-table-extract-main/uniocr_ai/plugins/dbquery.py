import sqlite3
from datetime import datetime
from common_module import write_log
from configs import etc_config, path_config

db_path = path_config['DB_PATH']

# 5. OCR 이력(MD-05) 삽입         GQ-07
def ocr_hist_insert(data, oid):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        cur.execute(
            'INSERT INTO "OCR_HIST"(DOC_NO, META_PTH, EXEC_TM, SUCCESS_AT, ERROR_MESSAGE, REGIST_DT) VALUES(?, ?, ?, ?, ?, ?)',
            (data['DOC_NO'], data['META_PTH'], data['EXEC_TM'], data['SUCCESS_AT'], data['ERROR_MESSAGE'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        con.commit()
        write_log("OCR 이력 삽입 성공", etc_config['LOG_LEVEL_INFO'], oid)
        return True
    except sqlite3.Error as err:
        con.rollback()
        write_log('ocr_hist_insert ' + str(err), etc_config['LOG_LEVEL_ERROR'], oid)
        return False
    finally:
        con.close()


def error_insert(data, oid):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        cur.execute(
            'INSERT INTO "ERROR_HIST"(ERROR_CODE, ERROR_MESSAGE, METHOD, OID, REGIST_DT) VALUES(?, ?, ?, ?, ?)',
            (data['ERROR_CODE'], data['ERROR_MESSAGE'], data['METHOD'], oid, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        con.commit()
        write_log("error insert success!", etc_config['LOG_LEVEL_INFO'], oid)
        return True
    except sqlite3.Error as err:
        con.rollback()
        write_log('error_insert ' + str(err), etc_config['LOG_LEVEL_ERROR'], oid)
        return False
    finally:
        con.close()


def make_db():
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # 5. OCR 이력(MD-05) 생성
    cur.execute('CREATE TABLE IF NOT EXISTS "OCR_HIST" ("DOC_NO"	TEXT, "META_PTH"	TEXT, 	"EXEC_TM"	REAL, 	"SUCCESS_AT"	INTEGER NOT NULL, "ERROR_MESSAGE"	TEXT, "REGIST_DT"	TEXT NOT NULL);')

    # 6. 에러로그(MD-06) 생성
    cur.execute('CREATE TABLE IF NOT EXISTS "ERROR_HIST" ("ERROR_CODE"	TEXT NOT NULL,  "ERROR_MESSAGE"	TEXT NOT NULL, "METHOD" TEXT NOT NULL, "OID"	TEXT NOT NULL, "REGIST_DT"	TEXT NOT NULL);')
    con.commit()
    con.close()