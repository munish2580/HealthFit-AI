import os
import sqlite3
from dotenv import load_dotenv
import mysql.connector
from flask import Flask, render_template, request, jsonify
from PIL import Image
import json
import google.generativeai as genai
import joblib
import numpy as np
import google_fit_api
import twilio_api

app = Flask(__name__)

# --- 1. CONFIGURATION ---
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

load_dotenv(override=True)
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)



# Smart Database Connection (MySQL primary with SQLite fallback for cloud deployment)
class SmartDB:
    def __init__(self):
        self.use_sqlite = False
        self.mysql_db = None
        self.mysql_cursor = None
        self.sqlite_conn = None
        self._last_sqlite_cursor = None

        try:
            db_host = os.getenv("DB_HOST", "localhost")
            db_user = os.getenv("DB_USER", "root")
            db_password = os.getenv("DB_PASSWORD", "")
            db_name = os.getenv("DB_NAME", "healthfit_db")
            
            self.mysql_db = mysql.connector.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                database=db_name,
                connect_timeout=3
            )
            self.mysql_cursor = self.mysql_db.cursor(dictionary=True)
            print("Connected to MySQL Database successfully.")
        except Exception as e:
            print(f"MySQL unavailable ({e}). Falling back to SQLite database for cloud hosting...")
            self.use_sqlite = True
            db_path = os.path.join(os.path.dirname(__file__), 'healthfit.db')
            self.sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            self.sqlite_conn.row_factory = sqlite3.Row
            self._init_sqlite_tables()

    def _init_sqlite_tables(self):
        cursor = self.sqlite_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                extracted_text TEXT,
                ai_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS smartwatch_vitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                heart_rate INTEGER,
                steps INTEGER,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.sqlite_conn.commit()

        # Seed initial vitals data if empty
        cursor.execute("SELECT COUNT(*) FROM smartwatch_vitals")
        if cursor.fetchone()[0] == 0:
            import random
            for i in range(1, 16):
                cursor.execute(
                    "INSERT INTO smartwatch_vitals (heart_rate, steps) VALUES (?, ?)",
                    (random.randint(65, 85), random.randint(4000, 9500))
                )
            self.sqlite_conn.commit()

    def execute(self, query, params=()):
        if self.use_sqlite:
            query_sqlite = query.replace('%s', '?')
            cursor = self.sqlite_conn.cursor()
            cursor.execute(query_sqlite, params)
            self._last_sqlite_cursor = cursor
            return cursor
        else:
            return self.mysql_cursor.execute(query, params)

    def fetchone(self):
        if self.use_sqlite:
            row = self._last_sqlite_cursor.fetchone()
            return dict(row) if row else None
        else:
            return self.mysql_cursor.fetchone()

    def fetchall(self):
        if self.use_sqlite:
            rows = self._last_sqlite_cursor.fetchall()
            return [dict(r) for r in rows] if rows else []
        else:
            return self.mysql_cursor.fetchall()

    def commit(self):
        if self.use_sqlite:
            self.sqlite_conn.commit()
        elif self.mysql_db:
            self.mysql_db.commit()

_smart_db = SmartDB()
db = _smart_db
cursor = _smart_db

# --- 2. THE DOCTOR PROMPT ---
def get_ai_doctor_response(input_data, source="report"):
    prompt = f"""
    You are a friendly, empathetic, and professional Patient Consultant explaining a medical report based on a {source}.
    Write in a natural, conversational, and easy-to-understand language. Speak directly to the patient (e.g., "Your report shows that...", "I recommend that you...").
    Use an encouraging and supportive tone. Avoid overly complex medical jargon, or explain it simply if you must use it.
    
    CRITICAL INSTRUCTION: You MUST classify the report into one of two categories: `NORMAL` or `ABNORMAL`.
    
    1. If NORMAL:
       - Give them good news first! Explain that their vitals and parameters look stable and healthy.
       - Suggest friendly, general wellness tips to keep up the good work.
    
    2. If ABNORMAL:
       - Gently inform them about the specific values that need attention.
       - Clearly explain any potential risks in a calm, non-alarming way.
       - Suggest practical, easy-to-follow interventions or lifestyle changes. Emphasize consulting a physical doctor for a final check.
       - Provide a structured but friendly dietary and lifestyle routine.

    For the physical therapy/exercise and diet recipes, provide a YouTube search link format. Format: `https://www.youtube.com/results?search_query=Name+of+Item`
    
    RETURN ONLY VALID JSON matching this structure:
    {{
      "status": "NORMAL" or "ABNORMAL",
      "diagnosis": "Friendly explanation of their report findings (e.g., 'I noticed that your fasting glucose is a bit high...').",
      "prediction": "Simple, supportive assessment of their health trajectory (e.g., 'If we manage your diet, you can easily get this under control.').",
      "medicine": "Clear, gentle recommendations on any suggested treatments or consulting a doctor.",
      "diet": {{
          "morning": {{ "desc": "Friendly morning diet tip.", "link": "https://www.youtube.com/results?search_query=Healthy+Oats+Recipe" }},
          "afternoon": {{ "desc": "Friendly afternoon diet tip.", "link": "https://www.youtube.com/results?search_query=Healthy+Salad+Recipe" }},
          "night": {{ "desc": "Friendly evening diet tip.", "link": "https://www.youtube.com/results?search_query=Light+Dinner+Recipe" }}
      }},
      "activity": {{
          "name": "Specific physical therapy or exercise",
          "desc": "Friendly instructions on how to do it",
          "youtube_link": "https://www.youtube.com/results?search_query=Anulom+Vilom"
      }}
    }}
    """
    try:
        load_dotenv(override=True)
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        if isinstance(input_data, Image.Image):
            response = model.generate_content([prompt, input_data])
        else:
            response = model.generate_content(prompt + "\n\nUser Input: " + str(input_data))
            
        raw_text = response.text
        raw_text = raw_text.replace('```json', '').replace('```', '').strip()
        return json.loads(raw_text)
    except Exception as e:
        print(f"AI Error: {e}")
        return str(e)


def get_chat_response(patient_text):
    prompt = f"""
    You are a Patient Consultant answering a direct patient query without a report.
    Patient says: "{patient_text}"
    
    1. If it's a MINOR issue (e.g. slight headache, minor stomach pain): Suggest a simple home remedy, diet care, or light exercise. Tell them they will be fine.
    2. If it's a MAJOR issue (e.g. chest pain, severe bleeding, continuous pain for days): Strictly warn them to visit a physical doctor immediately.
    
    Keep response short (under 60 words). Sound empathetic but strict. Plain text only.
    """
    try:
        load_dotenv(override=True)
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text.replace('*', '').strip()
    except Exception as e:
        return "System error. Please consult a doctor."

# --- 3. ROUTES ---

@app.route('/')
def index():
    # Pehle user report upload wale page par jayega
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    try:
        # Latest report fetch karna
        cursor.execute("SELECT * FROM medical_reports ORDER BY id DESC LIMIT 1")
        report_data = cursor.fetchone()
        
        # Graphs ke liye Smartwatch data
        cursor.execute("SELECT * FROM smartwatch_vitals ORDER BY id DESC LIMIT 15")
        vitals = cursor.fetchall()
        
        # AI Summary string ko JSON mein wapas convert karna
        ai_plan = None
        if report_data and report_data.get('ai_summary'):
            try:
                summary = report_data['ai_summary']
                ai_plan = summary if isinstance(summary, dict) else json.loads(summary)
            except Exception as json_err:
                print(f"JSON decode error: {json_err}")
                ai_plan = None

        chart_data = {
            "labels": [v['id'] for v in reversed(vitals)] if vitals else [],
            "hr": [v['heart_rate'] for v in reversed(vitals)] if vitals else [],
            "steps": [v['steps'] for v in reversed(vitals)] if vitals else []
        }

        return render_template('dashboard.html', ai_plan=ai_plan, chart_data=chart_data)
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('dashboard.html', ai_plan=None, chart_data={"labels": [], "hr": [], "steps": []})

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        try:
            file = request.files.get('file')
            if file and file.filename:
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(path)
                
                # Load the image to pass directly to Gemini Vision
                img = Image.open(path)
                
                # AI Doctor Logic -> Image is directly analyzed, no Tesseract needed.
                ai_result = get_ai_doctor_response(img, "medical report image")
                
                if isinstance(ai_result, dict):
                    cursor.execute("INSERT INTO medical_reports (user_name, extracted_text, ai_summary) VALUES (%s, %s, %s)",
                                   ("Patient", "Direct Vision Analysis", json.dumps(ai_result)))
                    db.commit()
                    from flask import redirect, url_for
                    return redirect(url_for('dashboard'))
                else:
                    error_msg = "Google API Limit Exceeded (429). Please wait 1 minute and try again." if "429" in str(ai_result) else f"Error: {ai_result}"
                    return render_template('upload.html', error=error_msg)
            else:
                return render_template('upload.html', error="Please select a valid medical report file to upload.")
        except Exception as e:
            print(f"Upload error: {e}")
            return render_template('upload.html', error=f"Upload processing error: {e}")
              
    return render_template('upload.html')

@app.route('/daily-track')
def daily_track():
    # Attempt to authenticate and fetch real smartwatch data from Google Fit
    service = google_fit_api.get_fit_service()
    
    real_steps = google_fit_api.fetch_daily_steps(service, days=7)
    real_hr = google_fit_api.fetch_daily_heart_rate(service, days=7)
    
    import random
    
    # Fallback to mock data if no data returned or API fails
    if not real_steps or len(real_steps) == 0:
        real_steps = [random.randint(4000, 10000) for _ in range(7)]
    if not real_hr or len(real_hr) == 0:
        real_hr = [random.randint(65, 85) for _ in range(7)]
        
    # Ensure we have exactly 7 days of data for the chart
    while len(real_steps) < 7: real_steps.insert(0, random.randint(4000, 10000))
    while len(real_hr) < 7: real_hr.insert(0, random.randint(65, 85))
    
    labels = [f"Day {i}" for i in range(1, 8)]
    hr = real_hr[-7:]
    steps = real_steps[-7:]
    
    # Simulating SpO2 and Stress based on HR
    spo2 = [min(100, max(90, 100 - (h > 80) * random.randint(1, 4))) for h in hr]
    stress = [min(100, max(10, int((h - 60) * 1.5 + random.randint(0, 10)))) for h in hr]
    
    chart_data = {
        "labels": labels,
        "hr": hr,
        "steps": steps,
        "spo2": spo2,
        "stress": stress
    }
    
    return render_template('daily_track.html', chart_data=chart_data, live_connected=bool(service))

@app.route('/analyze-progress', methods=['POST'])
def analyze_progress():
    data = request.json
    
    prompt = f"""
    You are a Medical Expert reviewing IoT Smartwatch data for the last 7 days.
    Data:
    Heart Rate: {data.get('hr')}
    SpO2 (Oxygen): {data.get('spo2')}
    Steps: {data.get('steps')}
    Stress Level: {data.get('stress')}
    
    Tell the patient how their health trajectory is going based on the data.
    If the data is normal and stable, provide a friendly, encouraging message (e.g., "Great job! Your vitals are stable. Keep up the good work and stay hydrated."). 
    If the data is concerning (high stress or low SpO2), provide a gentle, caring suggestion to rest or adjust their routine.
    Be natural, neutral, and friendly. Do NOT try to scare the patient. Respond in under 60 words. Plain text only, no markdown.
    """
    try:
        load_dotenv(override=True)
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        feedback_text = response.text.strip().replace('*', '')
        
        # Send SMS alert to user's mobile via Twilio
        sms_sent = twilio_api.send_health_alert(f"HealthFit Alert: {feedback_text}")
        
        return jsonify({"feedback": feedback_text, "sms_sent": sms_sent})
    except Exception as e:
        return jsonify({"feedback": "Error analyzing progress. Please consult doctor.", "sms_sent": False})

@app.route('/send-reminder', methods=['POST'])
def send_reminder():
    import random
    reminders = [
        "HealthFit Reminder: It's time to drink a glass of water! Stay hydrated.",
        "HealthFit Reminder: Don't forget to take a 5-minute walk and stretch your legs.",
        "HealthFit Reminder: Time for your healthy meal. Remember to eat balanced portions!",
        "HealthFit Reminder: Take a deep breath and relax for a minute to keep stress levels low."
    ]
    msg = random.choice(reminders)
    try:
        sms_sent = twilio_api.send_health_alert(msg)
        return jsonify({"feedback": msg, "sms_sent": sms_sent})
    except Exception as e:
        return jsonify({"feedback": "Error sending reminder.", "sms_sent": False})

@app.route('/doctor-chat')
def doctor_chat():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.form.get('message')
    if not msg:
        return jsonify({"response": "Please say something."})
    chat_reply = get_chat_response(msg)
    return jsonify({"response": chat_reply})

@app.route('/report-chat', methods=['POST'])
def report_chat():
    data = request.json
    msg = data.get('message')
    if not msg:
        return jsonify({"response": "Please ask a question."})
        
    # Fetch the latest report context (Retrieval step for RAG)
    cursor.execute("SELECT * FROM medical_reports ORDER BY id DESC LIMIT 1")
    report_data = cursor.fetchone()
    
    if not report_data or not report_data.get('ai_summary'):
        return jsonify({"response": "No active report found to analyze. Please upload a report first."})
        
    try:
        ai_plan = json.loads(report_data['ai_summary'])
        
        # Simple RAG implementation: Pass the report context to the model
        prompt = f"""
        You are a helpful Patient Consultant answering questions about a patient's medical report and their recommended daily routine.
        Here is the patient's current report summary and routine context:
        - Diagnosis: {ai_plan.get('diagnosis', 'N/A')}
        - Assessment: {ai_plan.get('prediction', 'N/A')}
        - Prescription: {ai_plan.get('medicine', 'N/A')}
        - Diet/Routine: {ai_plan.get('diet', 'N/A')}
        - Suggested Exercise: {ai_plan.get('activity', 'N/A')}
        
        The patient asks: "{msg}"
        
        Answer the patient's question concisely and accurately based ONLY on their report and routine context above. 
        You CAN answer questions about their diagnosis, medicines, diet, exercise, and daily routine.
        Be friendly and empathetic. Explain medical terms simply. If the question is completely unrelated to their health, report, or routine, politely say you can only answer questions related to their medical profile. Keep the response plain text and under 60 words.
        """
        load_dotenv(override=True)
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        chat_reply = response.text.replace('*', '').strip()
        return jsonify({"response": chat_reply})
    except Exception as e:
        return jsonify({"response": f"System error processing report query. {e}"})

@app.route('/risk-predictor', methods=['GET', 'POST'])
def risk_predictor():
    prediction = None
    probability = None
    
    if request.method == 'POST':
        try:
            age = float(request.form.get('age'))
            bp = float(request.form.get('bp'))
            cholesterol = float(request.form.get('cholesterol'))
            max_hr = float(request.form.get('max_hr'))
            stress = float(request.form.get('stress'))
            blood_sugar = float(request.form.get('blood_sugar', 90)) # default 90 if not provided
            bmi = float(request.form.get('bmi', 22)) # default 22 if not provided
            
            # Load model and scaler
            model_path = os.path.join(os.path.dirname(__file__), 'ml_model', 'heart_model.pkl')
            scaler_path = os.path.join(os.path.dirname(__file__), 'ml_model', 'scaler.pkl')
            
            heart_risk_prob = None
            if os.path.exists(model_path) and os.path.exists(scaler_path):
                try:
                    model = joblib.load(model_path)
                    scaler = joblib.load(scaler_path)
                    features = np.array([[age, bp, cholesterol, max_hr, stress]])
                    features_scaled = scaler.transform(features)
                    prob = model.predict_proba(features_scaled)[0][1]
                    heart_risk_prob = round(prob * 100, 1)
                except Exception as ml_err:
                    print(f"ML Model load error: {ml_err}. Using clinical algorithm fallback.")

            if heart_risk_prob is None:
                # Clinical Algorithm Fallback (Framingham / AHA Guidelines)
                base = 12.0
                base += (age - 30) * 0.4 if age > 30 else 0
                base += (bp - 120) * 0.35 if bp > 120 else 0
                base += (cholesterol - 180) * 0.25 if cholesterol > 180 else 0
                base += stress * 3.0
                if max_hr < 130: base += 8.0
                heart_risk_prob = round(max(5.0, min(95.0, base)), 1)
                
            # Diabetes Risk Calculation (Heuristic based on Medical Guidelines)
            diabetes_prob = 10
            if blood_sugar > 125:
                diabetes_prob = min(95, 50 + (blood_sugar - 125) * 1.5 + (bmi - 25) * 1.2)
            elif blood_sugar >= 100:
                diabetes_prob = min(50, 20 + (blood_sugar - 100) * 1.2 + (bmi - 25))
            else:
                diabetes_prob = max(5, 5 + (bmi - 25) * 0.5)
            diabetes_prob = round(max(5, min(95, diabetes_prob)), 1)
            
            # Overall Vitality Score (100 is best)
            vitality = 100
            vitality -= (age - 30) * 0.3 if age > 30 else 0
            vitality -= stress * 2
            vitality -= abs(bp - 120) * 0.4
            vitality -= abs(bmi - 22) * 1.5
            vitality -= abs(cholesterol - 180) * 0.1
            vitality += (max_hr - 150) * 0.2 if max_hr > 150 else 0
            vitality_score = round(max(10, min(99, vitality)), 1)
            
            prediction = {
                "heart": {
                    "probability": heart_risk_prob,
                    "label": "High Risk" if heart_risk_prob > 60 else "Moderate Risk" if heart_risk_prob > 30 else "Low Risk",
                    "color": "red" if heart_risk_prob > 60 else "yellow" if heart_risk_prob > 30 else "green"
                },
                "diabetes": {
                    "probability": diabetes_prob,
                    "label": "High Risk" if diabetes_prob > 60 else "Prediabetic" if diabetes_prob > 30 else "Normal",
                    "color": "red" if diabetes_prob > 60 else "yellow" if diabetes_prob > 30 else "green"
                },
                "vitality": {
                    "score": vitality_score,
                    "label": "Excellent" if vitality_score > 80 else "Good" if vitality_score > 60 else "Needs Attention",
                    "color": "green" if vitality_score > 80 else "yellow" if vitality_score > 60 else "red"
                }
            }
        except Exception as e:
            prediction = {"error": f"Error processing data: {e}"}
            
    return render_template('predictor.html', prediction=prediction)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)