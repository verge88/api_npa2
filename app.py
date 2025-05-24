import os
from flask import Flask, jsonify, request
from scraper import MeganormScraper
import logging

app = Flask(__name__)
app.config['JSON_ENSURE_ASCII'] = False

# Настройка логирования
logging.basicConfig(level=logging.INFO)

scraper = MeganormScraper()

@app.route('/')
def index():
    return jsonify({
        "message": "Meganorm API",
        "version": "1.0",
        "endpoints": {
            "/api/document-types": "Получить все типы документов",
            "/api/documents": "Получить документы по типу (параметр: type_url)",
            "/api/document": "Получить содержимое документа (параметр: url)",
            "/api/search": "Поиск документов (параметры: query, type, limit)"
        }
    })

@app.route('/api/document-types', methods=['GET'])
def get_document_types():
    """Получить все типы документов"""
    try:
        result = scraper.get_document_types()
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Получить документы определенного типа"""
    type_url = request.args.get('type_url')
    limit = int(request.args.get('limit', 50))
    
    if not type_url:
        return jsonify({
            "success": False,
            "error": "Параметр type_url обязателен"
        }), 400
    
    try:
        result = scraper.get_documents_by_type(type_url, limit)
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/document', methods=['GET'])
def get_document():
    """Получить полное содержимое документа"""
    doc_url = request.args.get('url')
    
    if not doc_url:
        return jsonify({
            "success": False,
            "error": "Параметр url обязателен"
        }), 400
    
    try:
        result = scraper.get_document_content(doc_url)
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/search', methods=['GET'])
def search_documents():
    """Поиск документов"""
    query = request.args.get('query')
    doc_type = request.args.get('type')
    limit = int(request.args.get('limit', 20))
    
    if not query:
        return jsonify({
            "success": False,
            "error": "Параметр query обязателен"
        }), 400
    
    try:
        result = scraper.search_documents(query, doc_type, limit)
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint не найден"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Внутренняя ошибка сервера"
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
