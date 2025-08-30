from flask import Flask, render_template, request, jsonify, send_file, session, url_for
import pandas as pd
import os
import json
from datetime import datetime
from config import Config, allowed_file
from ctgan_model import FinancialDataGenerator
import io
import random
import traceback
import numpy as np

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get('FLASK_SECRET') or 'financial-transaction-simulator-secret-key'

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Custom JSON encoder to handle NumPy / pandas types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        else:
            return super(NumpyEncoder, self).default(obj)

app.json_encoder = NumpyEncoder

# Global variable to store latest synthetic data (DataFrame)
latest_synthetic_data = None

# -------------------------
# Template filters/helpers
# -------------------------
@app.template_filter('format_number')
def format_number(value):
    try:
        return f"{int(value):,}"
    except Exception:
        return value

@app.template_filter('format_currency')
def format_currency(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return value

@app.context_processor
def inject_helpers():
    def get_random_color():
        colors = ["#007bff", "#28a745", "#ffc107", "#dc3545", "#6f42c1", "#20c997", "#17a2b8", "#fd7e14"]
        return random.choice(colors)
    return dict(get_random_color=get_random_color)

# -------------------------
# Routes
# -------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_data():
    global latest_synthetic_data

    try:
        # Read form parameters
        num_transactions = int(request.form.get('num_transactions', 1000))
        fraud_percentage = float(request.form.get('fraud_percentage', 2.0)) / 100.0
        time_range = request.form.get('time_range', '1 Month')
        transaction_type = request.form.get('transaction_type', 'Mixed')

        generator = FinancialDataGenerator()

        file_uploaded = False
        uploaded_df = None

        # If file present, try load it
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = os.path.join(app.config['UPLOAD_FOLDER'],
                                            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                    file.save(filename)
                    try:
                        # read with pandas; allow flexible separators
                        uploaded_df = pd.read_csv(filename)
                    except Exception:
                        # try with engine python
                        uploaded_df = pd.read_csv(filename, engine='python')
                    file_uploaded = True
                else:
                    error_msg = 'Invalid file format. Please upload a CSV file.'
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': error_msg}), 400
                    else:
                        return render_template('index.html', error=error_msg)

        # If file uploaded and read ok, preprocess and train on that; otherwise use sample data
        if file_uploaded and uploaded_df is not None and not uploaded_df.empty:
            # Preprocess generically
            processed = generator.preprocess_data(uploaded_df)
            generator.original_data = processed

            # Train with caution: if dataset is very large, reduce epochs/batch
            epochs = 30
            # reduce epochs for large datasets
            if len(processed) > 50000:
                epochs = 10

            generator.train_ctgan(processed, epochs=epochs)
        else:
            # Use built-in sample dataset
            sample = generator.generate_sample_data(2000, fraud_percentage)
            processed = generator.preprocess_data(sample)
            generator.original_data = processed
            generator.train_ctgan(processed, epochs=30)

        # Generate synthetic dataset (mirror schema)
        # We will attempt to adjust 'is_fraud' proportion if column exists
        adjust = None
        if 'is_fraud' in (generator.original_data.columns if generator.original_data is not None else []):
            adjust = {'is_fraud': fraud_percentage}

        synthetic_data = generator.generate_synthetic_data(num_transactions, adjust_target=adjust)

        # Ensure DataFrame
        if not isinstance(synthetic_data, pd.DataFrame):
            synthetic_data = pd.DataFrame(synthetic_data)

        # Save globally for download
        latest_synthetic_data = synthetic_data.copy()

        # Analyze (defensive)
        analysis = generator.analyze_data(synthetic_data)

        # Convert arrays / numpy for JSON
        def convert_numpy_types(obj):
            if isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(i) for i in obj]
            elif isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            else:
                return obj

        analysis = convert_numpy_types(analysis)

        # Prepare category_distribution and fraud_by_category if present
        category_distribution = []
        if 'category_distribution' in analysis:
            for category, count in analysis['category_distribution'].items():
                category_distribution.append({'category': category, 'count': int(count)})

        # Fallback: if there are any "<col>_distribution" entries in analysis, choose the largest
        if not category_distribution:
            # find any *_distribution entries and pick the first one as category distribution
            for k, v in analysis.items():
                if k.endswith('_distribution') and isinstance(v, dict):
                    for cat, cnt in v.items():
                        category_distribution.append({'category': cat, 'count': int(cnt)})
                    break

        fraud_by_category = []
        if 'fraud_by_category' in analysis:
            for category, count in analysis['fraud_by_category'].items():
                fraud_by_category.append({'category': category, 'count': int(count)})

        # Prepare sample_data: construct up to 10 rows using existing columns (safe)
        sample_data = []
        if not synthetic_data.empty:
            sample_df = synthetic_data.head(10)
            for _, row in sample_df.iterrows():
                record = {}
                for col in synthetic_data.columns:
                    val = row.get(col)
                    # friendly formatting for timestamps
                    if isinstance(val, (pd.Timestamp,)):
                        record[col] = val.isoformat()
                    elif isinstance(val, (np.integer,)):
                        record[col] = int(val)
                    elif isinstance(val, (np.floating,)):
                        record[col] = float(val)
                    else:
                        # toJSONable
                        try:
                            json.dumps(val, cls=NumpyEncoder)
                            record[col] = val
                        except Exception:
                            record[col] = str(val)
                sample_data.append(record)

        # Provide sensible defaults for risk patterns
        risk_patterns = analysis.get('risk_patterns', {})
        default_risk_patterns = {
            'micro_transactions': 0,
            'large_transactions': 0,
            'international_transactions': 0,
            'unusual_merchant_patterns': 0
        }
        for key in default_risk_patterns:
            if key not in risk_patterns:
                risk_patterns[key] = default_risk_patterns[key]

        # If AJAX request, return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            results = {
                'analysis': {
                    'total_transactions': int(analysis.get('total_transactions', 0)),
                    'fraud_count': int(analysis.get('fraud_count', 0)),
                    'total_amount': float(analysis.get('total_amount', 0) or 0),
                    'avg_transaction': float(analysis.get('avg_transaction', 0) or 0),
                    'risk_patterns': risk_patterns
                },
                'category_distribution': category_distribution,
                'fraud_by_category': fraud_by_category,
                'sample_data': sample_data
            }
            return jsonify(results)
        else:
            # Server-side render for non-AJAX
            return render_template('results.html', analysis=analysis, sample_data=sample_data)

    except Exception as e:
        error_trace = traceback.format_exc()
        print("Error in /generate:", str(e))
        print(error_trace)
        error_msg = f'An error occurred: {str(e)}'
        # helpful message for CTGAN errors
        if "CTGAN" in str(e) or "generator" in str(e):
            error_msg = "Model training failed. This might be due to insufficient data, unsupported column types or memory constraints. Try with a smaller dataset or fewer rows."

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 500
        else:
            return render_template('error.html', error=error_msg), 500

@app.route('/download/<format>')
def download_data(format):
    global latest_synthetic_data
    try:
        if latest_synthetic_data is None or latest_synthetic_data.empty:
            return jsonify({'error': 'No data available for download. Please generate data first.'}), 400

        output = io.BytesIO()
        if format == 'csv':
            latest_synthetic_data.to_csv(output, index=False)
            output.seek(0)
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name='synthetic_financial_data.csv'
            )
        elif format == 'json':
            # to_json returns string
            js = latest_synthetic_data.to_json(orient='records', date_format='iso')
            output.write(js.encode('utf-8'))
            output.seek(0)
            return send_file(
                output,
                mimetype='application/json',
                as_attachment=True,
                download_name='synthetic_financial_data.json'
            )
        else:
            return jsonify({'error': 'Invalid format'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers (these use templates)
@app.errorhandler(404)
def not_found_error(error):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Resource not found'}), 404
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def internal_error(error):
    error_msg = 'Internal server error. Please try again later.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': error_msg}), 500
    return render_template('error.html', error=error_msg), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
