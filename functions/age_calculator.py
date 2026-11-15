from datetime import date, datetime

def calculate_age(birth_date):
    try:
        born = datetime.strptime(birth_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Enter your date of birth in YYYY-MM-DD format.")
    today = date.today()
    if born > today:
        raise ValueError("Date of birth cannot be in the future.")

    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day
    if days < 0:
        months -= 1
        # Number of days in the previous month.
        import calendar
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]
    if months < 0:
        years -= 1
        months += 12

    return {"birth_date": born.isoformat(), "years": years, "months": months, "days": days}
