import json
import os
import time
from datetime import date

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from google import genai
from google.genai import types

load_dotenv()

from gemini_tools import LABELS, TOOLS, execute  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
RETRY_WORDS = ("503", "unavailable", "overloaded", "high demand")
client = genai.Client(api_key=API_KEY) if API_KEY and not API_KEY.startswith("your_") else None

MAX_MESSAGES = 24       # context window: latest N messages
MAX_CHARS = 24000       # hard cap on characters sent
MAX_TOOL_ROUNDS = 5

BASE_SYSTEM = """You are ActionAI, an intelligent, friendly AI assistant. You talk naturally like a normal chatbot and you also have tools.

DECIDE FOR EVERY MESSAGE:
1. Normal question (explanations, concepts, coding, writing, ideas, study help, opinions) -> answer directly. Do NOT call a tool.
2. Calculation (e.g. "15% of 450", "sqrt of 144", "12 * 8") -> call `calculator`.
3. Current weather of a place -> call `get_weather`.
4. Convert an amount between currencies -> call `convert_currency`.
5. Exact age from a date of birth -> call `calculate_age` (date must be YYYY-MM-DD; convert other formats yourself).
6. If a required detail is missing (city, amount, currency, birth date) -> ask ONE short clarifying question instead of guessing.

RULES:
- Questions ABOUT a topic ("how does currency conversion work?", "how does humidity affect weather?", "what is a percentage?") are explanations: answer directly, never run a tool.
- Use the conversation context. "What about Lahore?" after a weather question means the weather in Lahore. "And in EUR?" after a currency conversion means the same amount in EUR.
- Never invent live data. If a tool returns an error, explain it simply and suggest what to try.
- After a tool returns, state the result clearly with its units; for currency mention the rate and date.
- Reply in the same language the user writes in (English, Urdu, or Roman Urdu). Use Markdown and fenced code blocks for code. Be clear and concise.
- Today's date is {today}."""


def build_system(custom):
    system = BASE_SYSTEM.format(today=date.today().isoformat())
    custom = (custom or "").strip()[:1500]
    if custom:
        system += "\n\nUser's custom instructions (follow them when they do not conflict with the rules above):\n" + custom
    return system


def trim_history(messages):
    kept, total = [], 0
    for m in reversed(messages[-MAX_MESSAGES:]):
        total += len(m["content"])
        if total > MAX_CHARS:
            break
        kept.append(m)
    return list(reversed(kept))


def normalize(messages):
    merged = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n\n" + m["content"]
        else:
            merged.append({"role": m["role"], "content": m["content"]})
    while merged and merged[0]["role"] != "user":
        merged.pop(0)
    return merged


def is_busy(exc):
    return any(w in str(exc).lower() for w in RETRY_WORDS)


def friendly_error(exc):
    text = str(exc).lower()
    if is_busy(exc):
        return "Gemini is busy right now (high demand). Please wait a few seconds and send your message again."
    if "api key" in text or "permission" in text or "401" in text or "403" in text:
        return "The Gemini API key is invalid or missing. Check GEMINI_API_KEY in your .env file."
    if "429" in text or "quota" in text or "resource_exhausted" in text:
        return "Rate limit reached. Please wait a moment and try again."
    if any(k in text for k in ("timeout", "deadline", "connect", "getaddrinfo", "network", "errno", "resolve")):
        return "Could not reach Gemini. Check your internet connection and try again."
    if "not found" in text or "404" in text:
        return "Model not found. Check GEMINI_MODEL in your .env file."
    return f"Could not generate a reply ({type(exc).__name__}: {str(exc)[:160]})"


def line(obj):
    return json.dumps(obj, ensure_ascii=False) + "\n"


def run_model(model, base_contents, system):
    """One full turn with a tool loop. Yields NDJSON events."""
    contents = list(base_contents)
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=TOOLS,
        temperature=0.5,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    for _ in range(MAX_TOOL_ROUNDS):
        parts, calls = [], []
        for chunk in client.models.generate_content_stream(model=model, contents=contents, config=config):
            cand = chunk.candidates[0] if chunk.candidates else None
            if not cand or not cand.content or not cand.content.parts:
                continue
            for p in cand.content.parts:
                parts.append(p)
                if p.function_call:
                    calls.append(p.function_call)
                elif p.text and not getattr(p, "thought", False):
                    yield line({"text": p.text})
        if not calls:
            return
        contents.append(types.Content(role="model", parts=parts))
        responses = []
        for call in calls:
            name = call.name
            yield line({"tool_start": name, "label": LABELS.get(name, name)})
            result = execute(name, dict(call.args or {}))
            ok = "error" not in result
            yield line({"tool_done": name, "label": LABELS.get(name, name), "ok": ok,
                        "detail": result.get("error", "") if not ok else ""})
            responses.append(types.Part.from_function_response(name=name, response={"result": result}))
        contents.append(types.Content(role="user", parts=responses))
    yield line({"text": "\n\nI reached the tool-call limit for this request. Please try a simpler request."})


@app.route("/")
def index():
    return render_template("index.html", model=MODEL, configured=client is not None)


@app.route("/api/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify(error="GEMINI_API_KEY is not set. Add it to your .env file and restart."), 500

    data = request.get_json(silent=True) or {}
    messages = [
        {"role": m["role"], "content": str(m["content"])[:6000]}
        for m in data.get("messages", [])
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()
    ]
    if not messages or messages[-1]["role"] != "user":
        return jsonify(error="Type a message to get a reply."), 400

    system = build_system(data.get("system"))
    history = normalize(trim_history(messages))
    base = [
        types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
        for m in history
    ]

    def generate():
        models = [MODEL] + ([FALLBACK_MODEL] if FALLBACK_MODEL and FALLBACK_MODEL != MODEL else [])
        last_exc = None
        for model in models:
            for attempt in range(3):
                started = False
                try:
                    for event in run_model(model, base, system):
                        started = True
                        yield event
                    return
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    app.logger.warning("Gemini error (%s, try %d): %s", model, attempt + 1, exc)
                    if not is_busy(exc):
                        yield line({"error": friendly_error(exc)})
                        return
                    if started:
                        yield line({"reset": True})
                    if attempt < 2:
                        time.sleep(1.5 * (attempt + 1))
        yield line({"error": friendly_error(last_exc)})

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
