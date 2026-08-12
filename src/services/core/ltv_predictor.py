import os
import joblib
import pandas as pd
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join("data", "ltv_model.pkl")
ENCODER_PATH = os.path.join("data", "ltv_encoder.pkl")

class LTVPredictor:
    def __init__(self):
        self.model = None
        self.encoder = None
        self._load_model()
        
    def _load_model(self):
        if os.path.exists(MODEL_PATH) and os.path.exists(ENCODER_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.encoder = joblib.load(ENCODER_PATH)
                logger.info("LTV Model successfully loaded.")
            except Exception as e:
                logger.error(f"Failed to load LTV model: {e}")
        else:
            logger.info("LTV Model files not found. Predictor will return baseline predictions.")
            
    def predict_ltv(self, lead_data: Dict[str, Any]) -> float:
        """
        Predicts Lifetime Value (LTV) for a given lead.
        lead_data expects keys like: 'industry', 'budget', 'contact_role', 'initial_score'
        """
        if not self.model or not self.encoder:
            # Baseline heuristic if model isn't trained yet
            budget = float(lead_data.get("budget", 0))
            return budget * 1.5 if budget > 0 else 500.0
            
        try:
            # Prepare DataFrame
            df = pd.DataFrame([lead_data])
            
            # Encode categorical features
            categorical_cols = ['industry', 'contact_role']
            for col in categorical_cols:
                if col not in df.columns:
                    df[col] = "unknown"
                    
            encoded_cats = self.encoder.transform(df[categorical_cols])
            cat_df = pd.DataFrame(encoded_cats, columns=self.encoder.get_feature_names_out(categorical_cols))
            
            # Combine with numerical
            num_df = df.drop(columns=categorical_cols, errors='ignore')
            num_df = num_df.apply(pd.to_numeric, errors='coerce').fillna(0)
            
            X = pd.concat([num_df.reset_index(drop=True), cat_df.reset_index(drop=True)], axis=1)
            
            # Predict
            prediction = self.model.predict(X)[0]
            return float(prediction)
        except Exception as e:
            logger.error(f"LTV prediction error: {e}")
            budget = float(lead_data.get("budget", 0))
            return budget * 1.5 if budget > 0 else 500.0

predictor = LTVPredictor()

def predict_lead_ltv(lead_data: Dict[str, Any]) -> float:
    return predictor.predict_ltv(lead_data)
