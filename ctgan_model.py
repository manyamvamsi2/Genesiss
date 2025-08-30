import pandas as pd
import numpy as np
from ctgan import CTGAN
import warnings
import math

warnings.filterwarnings('ignore')


class FinancialDataGenerator:
    def __init__(self):
        self.ctgan_model = None
        self.original_data = None
        self.synthetic_data = None
        self.columns = None   # Keep schema

    def generate_sample_data(self, num_samples=10000, fraud_rate=0.02):
        """Fallback dataset if no CSV uploaded."""
        np.random.seed(42)
        data = pd.DataFrame({
            'transaction_id': range(1, num_samples + 1),
            'customer_id': np.random.randint(1000, 5000, num_samples),
            'amount': np.round(np.random.exponential(150, num_samples) + 10, 2),
            'merchant_category': np.random.choice(
                ['Retail', 'Online', 'Grocery', 'Food', 'Travel',
                 'Entertainment', 'Services', 'Utilities', 'Healthcare', 'Education'],
                num_samples),
            'transaction_type': np.random.choice(
                ['Purchase', 'Withdrawal', 'Transfer', 'Payment'], num_samples),
            'location': np.random.choice(
                ['Domestic', 'International'], num_samples, p=[0.85, 0.15]),
            'device_type': np.random.choice(
                ['Mobile', 'Desktop', 'ATM'], num_samples, p=[0.6, 0.3, 0.1]),
            'hour_of_day': np.random.randint(0, 24, num_samples),
            'is_weekend': np.random.choice([0, 1], num_samples, p=[0.7, 0.3]),
            'is_fraud': np.random.choice(
                [0, 1], num_samples, p=[1 - fraud_rate, fraud_rate])
        })

        # Random transaction dates
        dates = pd.date_range(end=pd.Timestamp.now(), periods=30).tolist()
        data['transaction_date'] = np.random.choice(dates, num_samples)

        # Fraud patterns
        fraud_mask = data['is_fraud'] == 1
        if fraud_mask.sum() > 0:
            data.loc[fraud_mask, 'amount'] *= np.random.lognormal(1.5, 1, fraud_mask.sum())
            data.loc[fraud_mask, 'location'] = 'International'
            data.loc[fraud_mask, 'device_type'] = np.random.choice(
                ['Mobile', 'Desktop'], fraud_mask.sum(), p=[0.7, 0.3])
            data.loc[fraud_mask, 'hour_of_day'] = np.random.randint(0, 6, fraud_mask.sum())
        return data

    def preprocess_data(self, data: pd.DataFrame):
        """Prepare uploaded dataset dynamically for CTGAN."""
        if data is None:
            raise ValueError("No data provided to preprocess")

        processed = data.copy()

        # Convert datetime-like columns
        for col in processed.columns:
            if np.issubdtype(processed[col].dtype, np.datetime64):
                processed[col] = processed[col].astype('int64') // 10**9
            elif processed[col].dtype == object:
                try:
                    parsed = pd.to_datetime(processed[col], errors='coerce')
                    if parsed.notna().sum() / len(parsed) > 0.5:
                        processed[col] = parsed.astype('int64') // 10**9
                except Exception:
                    pass

        # Object columns → strings (safe for CTGAN)
        for col in processed.select_dtypes(include=['object']).columns:
            processed[col] = processed[col].astype(str).fillna("Unknown")

        # Numeric NaN → median
        for col in processed.select_dtypes(include=[np.number]).columns:
            if processed[col].isna().all():
                processed[col] = processed[col].fillna(0)
            else:
                processed[col] = processed[col].fillna(processed[col].median())

        # Save schema
        self.columns = processed.columns.tolist()
        return processed

    def train_ctgan(self, data: pd.DataFrame, epochs: int = 30, batch_size: int = 500):
        """Train CTGAN dynamically (handles any schema)."""
        if data is None or len(data) == 0:
            raise ValueError("No data available for training")

        data_to_use = data.copy()

        # Detect discrete columns (objects + low-cardinality numeric)
        discrete_columns = []
        for col in data_to_use.columns:
            if data_to_use[col].dtype == object:
                discrete_columns.append(col)
            else:
                uniq = data_to_use[col].nunique(dropna=True)
                if 0 < uniq < 20:
                    discrete_columns.append(col)

        if batch_size > len(data_to_use):
            batch_size = max(32, len(data_to_use) // 4)

        self.ctgan_model = CTGAN(epochs=epochs, batch_size=batch_size)
        self.ctgan_model.fit(data_to_use, discrete_columns)

    def generate_synthetic_data(self, num_samples: int = 1000, adjust_target: dict = None):
        """Generate synthetic dataset with same schema as input CSV."""
        if self.ctgan_model is None:
            raise ValueError("Model not trained yet.")

        synthetic = self.ctgan_model.sample(num_samples)

        # Ensure same column order
        if self.columns:
            for col in self.columns:
                if col not in synthetic.columns:
                    synthetic[col] = np.nan
            synthetic = synthetic[self.columns]

        # Optional fraud adjustment
        if adjust_target:
            for col, desired in adjust_target.items():
                if col in synthetic.columns and 0 <= desired <= 1:
                    desired_count = int(num_samples * desired)
                    fraud_indices = synthetic[synthetic[col].astype(str).isin(['1', 'True', 'true'])].index
                    non_fraud_indices = synthetic.index.difference(fraud_indices)

                    if len(fraud_indices) > desired_count:
                        to_flip = np.random.choice(fraud_indices, len(fraud_indices) - desired_count, replace=False)
                        synthetic.loc[to_flip, col] = 0
                    elif len(fraud_indices) < desired_count:
                        to_flip = np.random.choice(non_fraud_indices, min(desired_count - len(fraud_indices), len(non_fraud_indices)), replace=False)
                        synthetic.loc[to_flip, col] = 1

        self.synthetic_data = synthetic
        return synthetic

    def analyze_data(self, data: pd.DataFrame):
        """Return insights only for available columns."""
        analysis = {"total_transactions": int(len(data)) if data is not None else 0}

        if data is None or data.empty:
            return analysis

        # Amount stats
        if "amount" in data.columns:
            analysis["total_amount"] = float(data["amount"].sum())
            analysis["avg_transaction"] = float(data["amount"].mean())

        # Fraud stats
        if "is_fraud" in data.columns:
            fraud_col = pd.to_numeric(data["is_fraud"], errors="coerce").fillna(0).astype(int)
            fraud_count = int(fraud_col.sum())
            analysis["fraud_count"] = fraud_count
            analysis["fraud_percentage"] = (fraud_count / len(data) * 100) if len(data) > 0 else 0

        # Category distribution (if exists)
        if "merchant_category" in data.columns:
            analysis["category_distribution"] = data["merchant_category"].value_counts().to_dict()

        if "is_fraud" in data.columns and "merchant_category" in data.columns:
            fraud_by_category = data[data["is_fraud"].astype(str).isin(["1", "True", "true"])]["merchant_category"].value_counts()
            analysis["fraud_by_category"] = fraud_by_category.to_dict()

        # Risk patterns
        risk_patterns = {}
        if "amount" in data.columns:
            large_threshold = data["amount"].quantile(0.95)
            micro_threshold = data["amount"].quantile(0.05)
            risk_patterns["large_transactions"] = int((data["amount"] > large_threshold).sum())
            risk_patterns["micro_transactions"] = int((data["amount"] < micro_threshold).sum())
        if "location" in data.columns:
            risk_patterns["international_transactions"] = int(
                data[data["location"].astype(str).str.lower() == "international"].shape[0]
            )
        if risk_patterns:
            analysis["risk_patterns"] = risk_patterns

        return analysis
