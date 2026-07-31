import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib

def create_synthetic_data(num_samples=1000):
    """
    Creates synthetic medical data for heart disease prediction.
    Features: Age, Blood Pressure, Cholesterol, Max Heart Rate, Stress Level
    Target: Target (0 = Low Risk, 1 = High Risk)
    """
    np.random.seed(42)
    
    # Generate features
    age = np.random.normal(50, 15, num_samples).astype(int)
    age = np.clip(age, 20, 90)
    
    bp = np.random.normal(120, 20, num_samples).astype(int)
    bp = np.clip(bp, 90, 200)
    
    cholesterol = np.random.normal(200, 50, num_samples).astype(int)
    cholesterol = np.clip(cholesterol, 120, 400)
    
    max_hr = np.random.normal(150, 25, num_samples).astype(int)
    max_hr = np.clip(max_hr, 70, 210)
    
    stress_level = np.random.randint(1, 11, num_samples) # 1 to 10
    
    # Base probability for having heart disease based on features
    risk_score = ((age - 50) * 0.05) + ((bp - 120) * 0.02) + ((cholesterol - 200) * 0.015) - ((max_hr - 150) * 0.01) + ((stress_level - 5) * 0.5)
    
    # Normalize risk score to roughly 0 to 1 range (sigmoid-like)
    prob = 1 / (1 + np.exp(-risk_score))
    
    # Add some random noise and classify
    target = (prob + np.random.normal(0, 0.1, num_samples) > 0.5).astype(int)
    
    df = pd.DataFrame({
        'Age': age,
        'Blood_Pressure': bp,
        'Cholesterol': cholesterol,
        'Max_HR': max_hr,
        'Stress_Level': stress_level,
        'Target': target
    })
    
    return df

def main():
    print("Generating synthetic data...")
    df = create_synthetic_data(2000)
    
    X = df.drop('Target', axis=1)
    y = df['Target']
    
    print("Scaling features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    print("Training Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    model.fit(X_scaled, y)
    
    accuracy = model.score(X_scaled, y)
    print(f"Model trained with training accuracy: {accuracy:.2f}")
    
    # Create directory if it doesn't exist
    model_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
        
    print(f"Saving model to {model_dir}...")
    joblib.dump(model, os.path.join(model_dir, 'heart_model.pkl'))
    joblib.dump(scaler, os.path.join(model_dir, 'scaler.pkl'))
    
    print("Done! Model is ready.")

if __name__ == '__main__':
    main()
