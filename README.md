# ActionAI – Advanced AI Assistant

One chatbot, one conversation: normal AI chat (Gemini) + smart tools (calculator, live weather,
currency conversion, age calculator). The AI decides by itself whether to answer directly,
run a tool, or ask a clarifying question.

## Setup
```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
python app.py
```
Open http://127.0.0.1:5000

`.env`: `GEMINI_API_KEY` (required), `GEMINI_MODEL`, `WEATHER_API_KEY` (optional; without it
Open-Meteo is used, no key needed).

## Structure
```
app.py            Flask server, streaming + tool-calling loop, retry/fallback, errors
gemini_tools.py   Tool declarations + safe execution
functions/        calculator, weather, currency, age_calculator
templates/ static/  Dashboard UI (Deep Navy + Electric Cyan)
```
