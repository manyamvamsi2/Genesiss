from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import os
import json
from config import Config
from ctgan_model import FinancialDataGenerator
import io
import random
import traceback
import numpy as np

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get('FLASK_SECRET') or 'financial-transaction-simulator-secret-key'

# Custom JSON encoder to handle special data types from NumPy/Pandas
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        else:
            return super(NumpyEncoder, self).default(obj)

app.json_encoder = NumpyEncoder

# --- Global variables ---
latest_synthetic_data = None
try:
    generator = FinancialDataGenerator(model_path='PS_20174392719_1491204439457_log.pkl')
except (FileNotFoundError, IOError) as e:
    print(f"CRITICAL ERROR: Could not load the model. The application will not work. Error: {e}")
    generator = None

# -------------------------
# Template Filters & Helpers
# -------------------------
@app.template_filter('format_number')
def format_number(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value

@app.template_filter('format_currency')
def format_currency(value):
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return value

# -------------------------
# Main Routes
# -------------------------
@app.route('/')
def index():
    if generator is None:
        error_msg = "The data generation model could not be loaded. Please ensure the .pkl file is present and not corrupted."
        return render_template('error.html', error=error_msg), 503
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_data():
    global latest_synthetic_data

    if generator is None:
        return jsonify({'error': "The data generation model is not available."}), 503

    try:
        num_transactions = int(request.form.get('num_transactions', 1000))
        fraud_percentage = float(request.form.get('fraud_percentage', 2.0)) / 100.0

        adjust = {'is_fraud': fraud_percentage}
        synthetic_data = generator.generate_synthetic_data(num_transactions, adjust_target=adjust)
        latest_synthetic_data = synthetic_data.copy()
        analysis = generator.analyze_data(synthetic_data)

        # --- FIX: Ensure chart data is correctly formatted into a list of objects ---
        category_distribution = []
        if analysis.get('category_distribution'):
            for category, count in analysis['category_distribution'].items():
                category_distribution.append({'category': str(category), 'count': int(count)})

        fraud_by_category = []
        if analysis.get('fraud_by_category'):
            for category, count in analysis['fraud_by_category'].items():
                fraud_by_category.append({'category': str(category), 'count': int(count)})
        
        sample_data = []
        if not synthetic_data.empty:
            sample_df = synthetic_data.head(10)
            sample_data = json.loads(sample_df.to_json(orient='records', date_format='iso'))

        results = {
            'analysis': {
                'total_transactions': analysis.get('total_transactions', 0),
                'fraud_count': analysis.get('fraud_count', 0),
                'total_amount': analysis.get('total_amount', 0),
                'avg_transaction': analysis.get('avg_transaction', 0),
                'risk_patterns': analysis.get('risk_patterns', {})
            },
            'category_distribution': category_distribution,
            'fraud_by_category': fraud_by_category,
            'sample_data': sample_data
        }
        return jsonify(results)

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in /generate endpoint: {e}\n{error_trace}")
        return jsonify({'error': f'An error occurred: {e}'}), 500

@app.route('/download/<format>')
def download_data(format):
    global latest_synthetic_data
    if latest_synthetic_data is None or latest_synthetic_data.empty:
        return jsonify({'error': 'No data available to download. Please generate data first.'}), 400

    output = io.BytesIO()
    if format == 'csv':
        latest_synthetic_data.to_csv(output, index=False)
        mimetype = 'text/csv'
        download_name = 'synthetic_financial_data.csv'
    elif format == 'json':
        js = latest_synthetic_data.to_json(orient='records', date_format='iso')
        output.write(js.encode('utf-8'))
        mimetype = 'application/json'
        download_name = 'synthetic_financial_data.json'
    else:
        return jsonify({'error': 'Invalid format specified.'}), 400

    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=download_name)

# -------------------------
# Error Handlers
# -------------------------
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error='Page Not Found (404)'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error='An internal server error occurred (500).'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
