import requests

def convert_currency(amount, from_currency, to_currency):
    amount = float(amount)
    source = from_currency.upper().strip()
    target = to_currency.upper().strip()
    if amount < 0:
        raise ValueError("Amount cannot be negative.")
    if len(source) != 3 or len(target) != 3:
        raise ValueError("Use three-letter currency codes, such as USD or PKR.")

    url = f"https://open.er-api.com/v6/latest/{source}"
    response = requests.get(url, timeout=12)
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "success":
        raise ValueError("The exchange-rate provider could not complete this conversion.")
    rates = data.get("rates", {})
    if target not in rates:
        raise ValueError(f"Currency {target} is not supported by the provider.")
    rate = float(rates[target])
    return {
        "amount": amount,
        "from_currency": source,
        "to_currency": target,
        "exchange_rate": rate,
        "converted_amount": round(amount * rate, 2),
        "rate_date": data.get("time_last_update_utc", "Not provided"),
        "provider": "ExchangeRate-API"
    }
