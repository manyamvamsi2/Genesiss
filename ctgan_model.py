import pandas as pd
import numpy as np
from ctgan import CTGAN
import warnings
import pickle
import os

warnings.filterwarnings('ignore')

class FinancialDataGenerator:
    def __init__(self, model_path='PS_20174392719_1491204439457_log.pkl'):
        """
        Initializes the generator by loading a pre-trained CTGAN model from a pickle file.
        """
        self.ctgan_model = None
        self.columns = None
        try:
            with open(model_path, 'rb') as f:
                self.ctgan_model = pickle.load(f)
            if hasattr(self.ctgan_model, '_metadata') and self.ctgan_model._metadata:
                 self.columns = list(self.ctgan_model._metadata.get('columns'))
        except FileNotFoundError:
            raise FileNotFoundError(f"Model file not found at '{model_path}'. Please place the .pkl file in the project's root directory.")
        except Exception as e:
            raise IOError(f"An error occurred while loading the model from '{model_path}': {e}")

    def generate_synthetic_data(self, num_samples: int = 1000, adjust_target: dict = None):
        """
        Generates a synthetic dataset and robustly adjusts the fraud percentage.
        """
        np.random.seed(None)

        if self.ctgan_model is None:
            raise ValueError("The CTGAN model is not loaded.")

        synthetic = self.ctgan_model.sample(num_samples)

        fraud_col_name = None
        possible_names = ['is_fraud', 'isFraud']
        for name in possible_names:
            if name in synthetic.columns:
                fraud_col_name = name
                break
        
        if fraud_col_name and adjust_target and 'is_fraud' in adjust_target:
            desired_percentage = adjust_target['is_fraud']
            if 0 <= desired_percentage <= 1:
                desired_count = int(num_samples * desired_percentage)
                synthetic[fraud_col_name] = pd.to_numeric(synthetic[fraud_col_name], errors='coerce').fillna(0).astype(int)
                
                current_fraud_indices = synthetic[synthetic[fraud_col_name] == 1].index
                non_fraud_indices = synthetic.index.difference(current_fraud_indices)
                current_fraud_count = len(current_fraud_indices)

                if current_fraud_count > desired_count:
                    to_flip_count = current_fraud_count - desired_count
                    indices_to_flip = np.random.choice(current_fraud_indices, to_flip_count, replace=False)
                    synthetic.loc[indices_to_flip, fraud_col_name] = 0
                elif current_fraud_count < desired_count:
                    to_flip_count = min(desired_count - current_fraud_count, len(non_fraud_indices))
                    indices_to_flip = np.random.choice(non_fraud_indices, to_flip_count, replace=False)
                    synthetic.loc[indices_to_flip, fraud_col_name] = 1

        if fraud_col_name and fraud_col_name != 'is_fraud':
            synthetic.rename(columns={fraud_col_name: 'is_fraud'}, inplace=True)
            if self.columns:
                self.columns = [col if col != fraud_col_name else 'is_fraud' for col in self.columns]
        
        return synthetic

    def analyze_data(self, data: pd.DataFrame):
        """
        Calculates and returns key statistics from the generated data.
        """
        analysis = {"total_transactions": int(len(data)) if data is not None else 0}
        if data is None or data.empty:
            return analysis

        if "amount" in data.columns:
            analysis["total_amount"] = float(data["amount"].sum())
            analysis["avg_transaction"] = float(data["amount"].mean())

        if "is_fraud" in data.columns:
            fraud_col = pd.to_numeric(data["is_fraud"], errors="coerce").fillna(0).astype(int)
            analysis["fraud_count"] = int(fraud_col.sum())

        category_col = None
        if 'merchant_category' in data.columns:
            category_col = 'merchant_category'
        elif 'type' in data.columns:
            category_col = 'type'
        else:
            for col_name in data.columns:
                if col_name in ['is_fraud', 'amount'] or 'balance' in col_name or 'id' in col_name:
                    continue
                
                if data[col_name].dtype == 'object' or data[col_name].nunique() < 20:
                    category_col = col_name
                    break

        if category_col:
            analysis["category_distribution"] = data[category_col].value_counts().to_dict()
            if "is_fraud" in data.columns:
                fraud_by_category = data[data["is_fraud"] == 1][category_col].value_counts()
                analysis["fraud_by_category"] = fraud_by_category.to_dict()

        # "Risk Patterns" calculation has been removed.
        
        return analysis
