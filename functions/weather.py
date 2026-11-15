import os
import requests

_CODES = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
          51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
          71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
          95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"}


def _weatherapi(city, api_key):
    r = requests.get("https://api.weatherapi.com/v1/current.json",
                     params={"key": api_key, "q": city, "aqi": "no"}, timeout=12)
    if r.status_code != 200:
        return None
    d = r.json()
    cur, loc = d["current"], d["location"]
    return {"city": loc["name"], "country": loc["country"], "local_time": loc["localtime"],
            "condition": cur["condition"]["text"], "temperature_c": cur["temp_c"],
            "feels_like_c": cur["feelslike_c"], "humidity_percent": cur["humidity"],
            "wind_kph": cur["wind_kph"], "provider": "WeatherAPI.com"}


def _open_meteo(city):
    g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                     params={"name": city, "count": 1, "language": "en"}, timeout=12)
    g.raise_for_status()
    results = g.json().get("results") or []
    if not results:
        return None
    p = results[0]
    w = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": p["latitude"], "longitude": p["longitude"], "timezone": "auto",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code"},
        timeout=12)
    w.raise_for_status()
    c = w.json()["current"]
    return {"city": p["name"], "country": p.get("country", ""), "local_time": c.get("time"),
            "condition": _CODES.get(c.get("weather_code"), "Unknown"), "temperature_c": c["temperature_2m"],
            "feels_like_c": c["apparent_temperature"], "humidity_percent": c["relative_humidity_2m"],
            "wind_kph": c["wind_speed_10m"], "provider": "Open-Meteo"}


def get_weather(city):
    city = (city or "").strip()
    if not city:
        raise ValueError("Please tell me which city.")
    key = os.getenv("WEATHER_API_KEY", "").strip()
    if key and not key.startswith("replace_with"):
        data = _weatherapi(city, key)
        if data:
            return data
    data = _open_meteo(city)
    if not data:
        return {"error": f"I couldn't find weather data for '{city}'."}
    return data
