from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.utils import secure_filename
import os
import redis
from celery import Celery
from reportlab.pdfgen import canvas
import secrets
import logging
from http import HTTPStatus

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['QUOTE_FOLDER'] = 'quotes'
app.secret_key = secrets.token_hex(16)
ALLOWED_EXTENSIONS = {'pdf', 'png'}
try:
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    redis_client.ping()
except redis.ConnectionError as e:
    print(f"Redis connection failed: {e}. Ensure redis-server is running.")
    redis_client = None
celery = Celery(app.name, broker='redis://localhost:6379/0')

# Mock in-memory store for quotes
quotes_db = []

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Serve static files (index.html, styles.css, script.js)
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return jsonify({'csrf_token': session['csrf_token']})

@app.route('/api/leads', methods=['POST'])
def sync_lead():
    data = request.json
    if not data or not all(key in data for key in ['first_name', 'last_name', 'email']):
        return jsonify({'error': 'Missing fields'}), HTTPStatus.BAD_REQUEST
    cache_key = f"lead_{data['email']}"
    if redis_client and redis_client.exists(cache_key):
        return jsonify({'message': 'Lead already synced'}), HTTPStatus.OK
    mock_response = {'id': secrets.token_hex(4), 'properties': data}
    if redis_client:
        redis_client.setex(cache_key, 3600, str(mock_response))
    send_sms.delay(data['email'], 'Welcome to Pinnacle Dynamics!')
    logger.info(f"Lead synced: {data['email']}")
    return jsonify({'message': 'Lead synced', 'id': mock_response['id']}), HTTPStatus.OK

@app.route('/api/leads', methods=['GET'])
def get_leads():
    cache_key = 'leads'
    if redis_client and redis_client.exists(cache_key):
        return jsonify(eval(redis_client.get(cache_key)))
    mock_leads = [{'id': '1', 'properties': {'firstname': 'Arnold', 'lastname': 'Masutha', 'email': 'arnold@example.com'}}]
    if redis_client:
        redis_client.setex(cache_key, 300, str(mock_leads))
    return jsonify(mock_leads)

@app.route('/api/documents', methods=['POST'])
def upload_document():
    if request.form.get('csrf_token') != session.get('csrf_token'):
        return jsonify({'error': 'Invalid CSRF token'}), HTTPStatus.FORBIDDEN
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), HTTPStatus.BAD_REQUEST
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(file_path)
            logger.info(f"File uploaded: {filename}")
            return jsonify({'message': 'File uploaded'}), HTTPStatus.OK
        except Exception as e:
            logger.error(f"File upload failed: {str(e)}")
            return jsonify({'error': 'Failed to save file'}), HTTPStatus.INTERNAL_SERVER_ERROR
    return jsonify({'error': 'Invalid file type'}), HTTPStatus.BAD_REQUEST

@app.route('/api/quotes', methods=['POST'])
def generate_quote():
    data = request.json
    if not data or not data.get('contact_id') or not data.get('items'):
        return jsonify({'error': 'Missing fields'}), HTTPStatus.BAD_REQUEST
    contact_id, items = data['contact_id'], data['items']
    quote_id = secrets.token_hex(4)
    filename = f"quote_{contact_id}_{quote_id}.pdf"
    try:
        c = canvas.Canvas(os.path.join(app.config['QUOTE_FOLDER'], filename))
        c.drawString(100, 750, f"Quote for Contact {contact_id}")
        y = 700
        for item, price in items:
            c.drawString(100, y, f"{item}: R{price:.2f}")
            y -= 20
        c.save()
        quote = {'id': quote_id, 'contact_id': contact_id, 'items': items, 'version': 1, 'filename': filename}
        quotes_db.append(quote)
        logger.info(f"Quote generated: {quote_id}")
        return jsonify({'message': 'Quote generated', 'id': quote_id}), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Quote generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate quote'}), HTTPStatus.INTERNAL_SERVER_ERROR

@app.route('/api/quotes', methods=['GET'])
def get_quotes():
    return jsonify(quotes_db)

@app.route('/api/quotes/revise/<quote_id>', methods=['POST'])
def revise_quote(quote_id):
    data = request.json
    if not data or not data.get('items'):
        return jsonify({'error': 'Missing items'}), HTTPStatus.BAD_REQUEST
    for quote in quotes_db:
        if quote['id'] == quote_id:
            quote['items'] = data['items']
            quote['version'] += 1
            filename = f"quote_{quote['contact_id']}_{quote_id}_v{quote['version']}.pdf"
            try:
                c = canvas.Canvas(os.path.join(app.config['QUOTE_FOLDER'], filename))
                c.drawString(100, 750, f"Quote for Contact {quote['contact_id']} (v{quote['version']})")
                y = 700
                for item, price in quote['items']:
                    c.drawString(100, y, f"{item}: R{price:.2f}")
                    y -= 20
                c.save()
                quote['filename'] = filename
                logger.info(f"Quote revised: {quote_id} (v{quote['version']})")
                return jsonify({'message': 'Quote revised', 'id': quote_id}), HTTPStatus.OK
            except Exception as e:
                logger.error(f"Quote revision failed: {str(e)}")
                return jsonify({'error': 'Failed to revise quote'}), HTTPStatus.INTERNAL_SERVER_ERROR
    return jsonify({'error': 'Quote not found'}), HTTPStatus.NOT_FOUND

@app.route('/api/schedule', methods=['POST'])
def schedule_activity():
    data = request.json
    if not data or not all(key in data for key in ['contact_id', 'date', 'type']):
        return jsonify({'error': 'Missing fields'}), HTTPStatus.BAD_REQUEST
    mock_response = {'id': secrets.token_hex(4), 'engagement': data}
    send_whatsapp.delay(data['contact_id'], f"Activity {data['type']} scheduled!")
    logger.info(f"Activity scheduled for {data['contact_id']}")
    return jsonify({'message': 'Activity scheduled'}), HTTPStatus.OK

@celery.task
def send_sms(email, message):
    logger.info(f"Mock SMS sent to {email}: {message}")

@celery.task
def send_whatsapp(contact_id, message):
    logger.info(f"Mock WhatsApp sent to {contact_id}: {message}")

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['QUOTE_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)