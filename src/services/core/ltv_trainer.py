import os
import joblib
import pandas as pd
import logging
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from src.database import get_db
from src.services.utils.db_rows import fetch_rows

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join("data", "ltv_model.pkl")
ENCODER_PATH = os.path.join("data", "ltv_encoder.pkl")

async def train_ltv_model():
    """
    Fetches historical closed-won deals and trains a RandomForest model to predict LTV.
    Saves the model and encoder to disk.
    """
    logger.info("Starting LTV model training...")
    try:
        # Fetch historical data (example query based on a hypothetical 'leads' table)
        db = get_db()
        rows = await fetch_rows(
            db,
            """
            SELECT industry, contact_role, initial_budget as budget, final_ltv
            FROM historical_leads
            WHERE final_ltv IS NOT NULL AND final_ltv > 0
            """,
        )
        if not rows:
            logger.warning("Not enough historical data to train LTV model.")
            return False

        # Convert to DataFrame
        df = pd.DataFrame(rows)
        
        if len(df) < 10:
            logger.warning("Dataset too small for reliable LTV training. Minimum 10 rows required.")
            return False

        y = df['final_ltv'].astype(float)
        X_raw = df.drop(columns=['final_ltv'])
        X_raw['budget'] = pd.to_numeric(X_raw['budget'], errors='coerce').fillna(0)

        # Encode categorical
        categorical_cols = ['industry', 'contact_role']
        for col in categorical_cols:
            if col not in X_raw.columns:
                X_raw[col] = "unknown"
                
        encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
        encoded_cats = encoder.fit_transform(X_raw[categorical_cols])
        cat_df = pd.DataFrame(encoded_cats, columns=encoder.get_feature_names_out(categorical_cols))

        # Combine
        num_df = X_raw.drop(columns=categorical_cols)
        X = pd.concat([num_df.reset_index(drop=True), cat_df.reset_index(drop=True)], axis=1)

        # Train Model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        # Save artifacts
        os.makedirs("data", exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        joblib.dump(encoder, ENCODER_PATH)

        # Force predictor to reload
        from src.services.core.ltv_predictor import predictor
        predictor._load_model()
        
        logger.info(f"LTV model trained successfully on {len(df)} records. R^2 score: {model.score(X, y):.2f}")
        return True

    except Exception as e:
        logger.error(f"Failed to train LTV model: {e}", exc_info=True)
        return False