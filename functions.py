
import requests
import json, os, smtplib
from email.mime.text import MIMEText
import re
from typing import Dict
import requests

payload = {
    "cid": "tnuabm",
    "user": "mr0523794544",
    "pass": "1e091a",
    "lang": "he",
    "token": "CARD3E8-C0A82A0C-68F10B48-470260DF",
    "sum": 0.1,
    "currency_code": "ILS",
    "description": "בדיקת חיוב חוזר"
}

r = requests.post("https://api.icount.co.il/api/v3.php/pay/bytoken", json=payload)

REGISTRATIONS_FILE = 'registrations.json'
COURSES_FILE = 'courses.json'

ICOUNT_API_URL = "https://api.icount.co.il/api/v3.php/doc/create"
# BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://karly-doziest-tubulously.ngrok-free.dev")

ICOUNT_SUCCESS_URL = "https://karly-doziest-tubulously.ngrok-free.dev/payment_success"
ICOUNT_ERROR_URL = "https://karly-doziest-tubulously.ngrok-free.dev/payment_fail"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

FAILED_LOGINS = {}
MAX_ATTEMPTS = 3
LOCK_TIME = 60 * 30   # חצי שעה חסימה

PENDING_FILE = 'pending.json'
PRICES_FILE = 'prices.json'



def load_prices():
    if not os.path.exists(PRICES_FILE):
        # יצירת קובץ ברירת מחדל אם לא קיים
        default_prices = {"small": 350, "regular": 280 ,"months": 5}
        with open(PRICES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_prices, f, ensure_ascii=False, indent=2)
    with open(PRICES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_prices(prices):
    with open(PRICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

def load_pending() -> Dict[str, dict]:
    if not os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(PENDING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_pending(d: Dict[str, dict]):
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)




def validate_email(email):
    email = email.strip()
    if not email:
        return False
    # בדיקה בסיסית: חייב להכיל @ ולהיות סיומת
    pattern = r'^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$'
    return re.fullmatch(pattern, email) is not None

def validate_name(name):
    if not name or not name.strip():
        return False
    if len(name) > 50:
        return False
    # רק אותיות בעברית ורווחים
    if not re.fullmatch(r"[א-ת\s]+", name):
        return False
    return True

def load_json(file_path, default_data):
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_email(subject, body):
    sender_email = "elishevatruz1@gmail.com"
    sender_password = "wvkb texk wpku iawb"
    recipient_email = "elishevatruz1@gmail.com"
    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
    except Exception as e:
        print(f"שגיאה בשליחת מייל: {e}")
# def admin_panel():

#     courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})
#     prices = load_json('prices.json', {"small": 350, "regular": 280, "months": 5, "registration_active": True})
    
#     # וידוא שיש שדה registration_active
#     if 'registration_active' not in prices:
#         prices['registration_active'] = True
#         save_json('prices.json', prices)
    
#     registration_active = prices.get('registration_active', True)
    
#     return render_template(
#         'admin_panel.html', 
#         courses=courses, 
#         prices=prices,
#         registration_active=registration_active
#     )





def load_prices_from_db(db):
    rows = db.session.execute(
        db.text("""
            select
                name,
                price,
                duration_months
            from course_types
        """)
    ).mappings().all()

    prices = {}
    for row in rows:
        prices[row["name"]] = row["price"]
        prices["months"] = row["duration_months"]

    # כרגע נשים קבוע. אפשר להעביר לטבלת settings בהמשך
    prices["registration_active"] = True

    return prices

def load_courses_from_db(db):
    rows = db.session.execute(
        db.text("""
            select
                c.course_name,
                c.gender,
                ct.name as course_type,
                cg.capacity
            from courses c
            join course_groups cg on cg.course_id = c.id
            join course_types ct on ct.id = cg.course_type_id
            order by c.course_name
        """)
    ).mappings().all()

    courses = {"boys": {}, "girls": {}}

    for row in rows:
        gender = row["gender"]
        course_name = row["course_name"]
        course_type = row["course_type"]

        if course_name not in courses[gender]:
            courses[gender][course_name] = {}

        courses[gender][course_name][course_type] = {
            "capacity": row["capacity"]
        }

    return courses

