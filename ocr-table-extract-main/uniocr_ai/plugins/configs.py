import configparser

properties = configparser.ConfigParser()
properties.read('./config.ini')

path_config = properties['PATH']
etc_config = properties['ETC']
pdf_config = properties['PDF'] 
ocr_config = properties['OCR']
tatr_config = properties['TATR']
detectron_config = properties['Detectron']

file_ext = properties['WF']['FILE_POS_EXT']
native_file_ext = ['jpg', 'jpeg', 'jpe', 'bmp', 'png', 'gif', 'tiff', 'tif', 'pdf']
conv_file_ext = [
    ext for ext in file_ext.lower().split(',')
    if ext not in native_file_ext
]