from flask import request

def register(app):
    from api.path_ocr import path_ocr

    @app.route("/path-ocr", methods=['POST'])
    def api_path_ocr():
        return path_ocr(request)