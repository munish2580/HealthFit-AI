# 🏥 HealthFit AI — Intelligent Personal Health Platform

<p align="center">
  <img src="static/logo.png" alt="HealthFit Logo" width="120"/>
</p>

<p align="center">
  <b>An AI-powered health monitoring and prediction platform built with Flask, Google Gemini, and IoT integration.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python"/>
  <img src="https://img.shields.io/badge/Flask-Web%20App-green?style=for-the-badge&logo=flask"/>
  <img src="https://img.shields.io/badge/Google%20Gemini-AI%20Powered-orange?style=for-the-badge&logo=google"/>
  <img src="https://img.shields.io/badge/Twilio-SMS%20Alerts-red?style=for-the-badge&logo=twilio"/>
</p>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🩺 **AI Medical Report Analyzer** | Upload a medical report image → Gemini AI gives diagnosis, diet plan & exercise |
| 💬 **AI Doctor Chatbot** | Ask health questions and get instant, empathetic AI responses |
| 📊 **Patient Dashboard** | Live charts for heart rate, steps, SpO2 & stress |
| ⌚ **Google Fit Integration** | Connects to real smartwatch data via Google Fit API |
| ❤️ **Multi-Risk Predictor** | ML model predicts Heart Disease, Diabetes & Vitality Score |
| 📱 **SMS Health Alerts** | Automated health reminders sent via Twilio SMS |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- MySQL Server
- Google account (for Google Fit)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/healthfit-ai.git
cd healthfit-ai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your actual API keys (see Configuration below)

# 4. Set up MySQL database
# Create a database named 'healthfit_db' and run the required table setup

# 5. Run the application
python app.py
```

Then open: **http://localhost:5000**

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
GEMINI_API_KEY=your_google_gemini_api_key
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=healthfit_db
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
TARGET_PHONE_NUMBER=+91xxxxxxxxxx
```

### Getting API Keys:
- **Gemini API Key** → [Google AI Studio](https://aistudio.google.com/app/apikey) *(Free tier available)*
- **Twilio** → [Twilio Console](https://console.twilio.com) *(Free trial available)*
- **Google Fit** → [Google Cloud Console](https://console.cloud.google.com) → Enable Fitness API → Download `credentials.json`

---

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **AI/ML**: Google Gemini 2.5 Flash, Scikit-learn (Heart Disease ML Model)
- **Database**: MySQL
- **IoT/Wearables**: Google Fit API
- **SMS**: Twilio
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js

---

## 📁 Project Structure

```
healthfit-ai/
├── app.py              # Main Flask application
├── google_fit_api.py   # Google Fit integration
├── twilio_api.py       # SMS alert module
├── ml_model/           # Trained ML model files
│   ├── heart_model.pkl
│   └── scaler.pkl
├── templates/          # HTML templates
├── static/             # CSS, JS, images
├── .env.example        # Environment variable template
└── requirements.txt    # Python dependencies
```

---

## ⚠️ Important Notes

- **Never commit** your `.env` file or `credentials.json` to GitHub
- The `uploads/` folder contains patient data — it is gitignored for privacy
- Google Fit token (`token.pickle`) needs to be regenerated locally after OAuth

---

## 👨‍💻 Author

Made with ❤️ by **[Your Name]**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin)](https://linkedin.com/in/YOUR_PROFILE)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=for-the-badge&logo=github)](https://github.com/YOUR_USERNAME)

---

## 📄 License

This project is for educational purposes. Feel free to fork and build upon it!
