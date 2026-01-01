from time import time
from flask import session, redirect, url_for
from flask import flash
from openpyxl import Workbook
from flask import send_file
import io
import requests
from flask import Flask, render_template, request
import json, os, smtplib
from email.mime.text import MIMEText
import re
import uuid
from typing import Dict
from urllib.parse import parse_qs


app = Flask(__name__)

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
print(r.status_code)
print(r.text)

REGISTRATIONS_FILE = 'registrations.json'
COURSES_FILE = 'courses.json'

ICOUNT_API_URL = "https://api.icount.co.il/api/v3.php/doc/create"
# BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://karly-doziest-tubulously.ngrok-free.dev")

ICOUNT_SUCCESS_URL = "https://karly-doziest-tubulously.ngrok-free.dev/payment_success"
ICOUNT_ERROR_URL = "https://karly-doziest-tubulously.ngrok-free.dev/payment_fail"



PENDING_FILE = 'pending.json'

def load_pending() -> Dict[str, dict]:
    if not os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(PENDING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_pending(d: Dict[str, dict]):
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

@app.route("/icount_webhook", methods=["POST"])
def icount_webhook():
    payload = request.get_json(silent=True) or {}
    if not payload and request.form:
        payload = request.form.to_dict(flat=True)

    print("iCount WEBHOOK RAW:", json.dumps(payload, ensure_ascii=False))

    # ניסיון שליפה ישיר
    order_ref = (
        payload.get("more")
        or payload.get("reference")
        or request.args.get("more")
        or request.args.get("reference")
    )
    # ניסיון מתוך utm_campaign בסגנון "93?more=UUID"
    if not order_ref:
        order_ref = _extract_more_from_utm(payload.get("utm_campaign"))

    if not order_ref:
        print("WEBHOOK: missing order_ref (no 'more' in payload or utm_campaign)")
        return "OK", 200

    # טעינת ה-pending וסגירת ההזמנה
    pending = load_pending()
    entry = pending.pop(order_ref, None)
    save_pending(pending)

    if not entry:
        print(f"WEBHOOK: order_ref {order_ref} not found in pending")
        return "OK", 200

    # אימות בסיסי להצלחה. אצלך חזרו doctype=receipt, docnum, confirmation_code
    success_flag = (
        str(payload.get("doctype", "")).lower() == "receipt"
        and payload.get("docnum")
        and payload.get("confirmation_code")
    )
    if not success_flag:
        print(f"WEBHOOK: order_ref {order_ref} missing success flags, proceeding anyway")

    # עדכון אסמכתאות מה־IPN לשמירה ברשומה
    entry["payment_status"] = "שולם"
    entry.setdefault("icount", {})
    entry["icount"].update({
        "docnum": payload.get("docnum"),
        "doc_url": payload.get("doc_url"),
        "confirmation_code": payload.get("confirmation_code"),
        "cc_type": payload.get("cc_type"),
        "cc_last4": payload.get("cc_last4"),
        "sum": payload.get("sum"),
        "currency_code": payload.get("currency_code"),
        "payment_date": payload.get("payment_date")
        # "card_token": payload.get("card_token")
    })
    # שמירת טוקן הכרטיס אם הגיע ב-IPN
    token = (
        payload.get("card_token")
        or payload.get("cc_token")
        or payload.get("token")
        or payload.get("token_id")
        or payload.get("cc_token_id")
    )
    entry.setdefault("icount", {})
    entry["icount"]["card_token"] = token
    # נוח גם להחזיק העתק בשורש הרשומה
    entry["card_token"] = token
        

    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})
    data["registered"].append(entry)
    save_json(REGISTRATIONS_FILE, data)

    # מייל כמו אצלך
    email_body = f"""
שם ההורה: {entry['parent_name']} {entry['parent_surname']}
אימייל: {entry['email']}
טלפון: {entry['phone']}
שם הילד/ה: {entry['child_name']}
גיל: {entry['child_age']}
מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}
קורס: {entry['course']}
קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}
סכום לתשלום: {entry['amount_to_pay']} ש"ח

אסמכתא: {entry['icount'].get('confirmation_code')}
מסמך: {entry['icount'].get('docnum')}
לינק למסמך: {entry['icount'].get('doc_url')}
כרטיס: {entry['icount'].get('cc_type')} ****{entry['icount'].get('cc_last4')}
"""
    if "insurance" in entry:
        email_body += f"\nקופת חולים: {entry['insurance']}"
        email_body += f"\nהתחייבויות: {entry.get('commitments','לא')}"

    send_email("רישום חדש לקורס", email_body)
    print(f"WEBHOOK: order {order_ref} finalized")
    return "OK", 200

def _extract_more_from_utm(val: str):
    if not val:
        return None
    # לדוגמה "93?more=68d4a17d-..."
    if "?" in val:
        q = val.split("?", 1)[1]
        qs = parse_qs(q)
        m = qs.get("more", [None])[0]
        return m
    return None


@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html")

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

# @app.route('/', methods=['GET','POST'])
# def register():
#     data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})
#     data.setdefault('registered', [])
#     data.setdefault('waiting_list', [])
#     courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})
#     error_msg = None
#     success_msg = None

#     course_status = {}

#     if request.method == 'POST':
#         parent_name = request.form.get('parent_name')
#         parent_surname = request.form.get('parent_surname')
#         email = request.form.get('email')
#         phone = request.form.get('phone')
#         child_name = request.form.get('child_name')
#         child_age = int(request.form.get('child_age'))
#         child_gender = request.form.get('child_gender')
#         course = request.form.get('course')
#         group_type = request.form.get('group_type')
 

#         phone_pattern =  re.compile(r'^(?:\+972|0)(?:5\d\d{7}|[23489]\d{7})$')

#         try:
#             child_age = int(request.form.get('child_age'))
#         except (ValueError, TypeError):
#             error_msg = "אנא הכנס גיל תקין במספרים."
#             flash(error_msg, 'error')
#             return redirect(url_for('register'))


#         if not phone_pattern.match(phone):
#             error_msg = "מספר טלפון לא חוקי. אנא הכנס מספר תקין, לדוגמה נייד 0521234567 או קו בית 03-1234567"
#         elif not validate_email(email):
#             error_msg = "האימייל אינו חוקי. יש להכניס כתובת אימייל תקינה."
#         elif not validate_name(parent_name):
#             error_msg = "שם ההורה אינו חוקי. יש להשתמש רק באותיות בעברית."
#         elif not validate_name(parent_surname):
#             error_msg = "שם המשפחה אינו חוקי. יש להשתמש רק באותיות בעברית."
#         elif not validate_name(child_name):
#             error_msg = "שם המשפחה אינו חוקי. יש להשתמש רק באותיות בעברית."
        
#         elif not all([parent_name,parent_surname,email,phone,child_name,child_age,child_gender,course,group_type]):
#             error_msg = "אנא מלא/י את כל השדות."
#         else:
#             # בדיקת גיל
#             age_range = courses[child_gender][course][group_type]["age_range"]
#             if not (age_range[0] <= child_age <= age_range[1]):
#                     error_msg = f"הגיל של הילד/ה לא מתאים ל{ 'קבוצה קטנה' if group_type == 'small' else 'קבוצה רגילה' } (טווח גילאים: {age_range[0]}-{age_range[1]})."

#             else:
#                 # חישוב אם הקורס מלא
#                 max_spots = courses[child_gender][course][group_type]["capacity"]
#                 current_count = sum(
#                     1 for r in data['registered']
#                     if r['course'] == course and r['group_type'] == group_type
#                 )
#                 max_spots = courses[child_gender][course][group_type]["capacity"]
#                 is_full = current_count >= max_spots

#                 entry = {
#                     "parent_name": parent_name,
#                     "parent_surname": parent_surname,
#                     "email": email,
#                     "phone": phone,
#                     "child_name": child_name,
#                     "child_age": child_age,
#                     "child_gender": child_gender,
#                     "course": course,
#                     "group_type": group_type
#                 }
#                 payment_type = request.form.get("payment_type")
#                 if payment_type == "insurance":
#                     insurance = request.form.get("insurance")
#                     commitments = "לא"
#                     entry["insurance"] = insurance
#                     entry["commitments"] = commitments
#                 prices = load_json('prices.json', {"small": 350, "regular": 280, "months": 5})
#                 if payment_type == "insurance":
#                     amount_to_pay = 100
#                 else:
#                     if group_type == "small":
#                         amount_to_pay = prices["small"] * prices.get("months", 1)
#                     else:
#                         amount_to_pay = prices["regular"] * prices.get("months", 1)

#                 entry["amount_to_pay"] = amount_to_pay




#                 if not is_full:
#                     data['registered'].append(entry)
#                     success_msg = f"ההרשמה שלך לקורס '{course}' ({ 'קבוצה קטנה' if group_type == 'small' else 'קבוצה רגילה' } ) התקבלה בהצלחה!"
#                     email_body = f"""

#                     שם ההורה: {entry['parent_name']} {entry['parent_surname']}
#                     אימייל: {entry['email']}
#                     טלפון: {entry['phone']}

#                     שם הילד/ה: {entry['child_name']}
#                     גיל: {entry['child_age']}
#                     מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}

#                     קורס: {entry['course']}
#                     קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}
#                     """

#                     # אם יש שדות נוספים כמו ביטוח/התחייבות – נוסיף
#                     if "insurance" in entry:
#                         email_body += f"\nקופת חולים: {entry['insurance']}"
#                         email_body += f"\nהתחייבויות: {entry.get('commitments','לא')}"

#                     send_email(f"רישום חדש לקורס {course}", email_body)
                    
#                     # send_email(f"רישום חדש לקורס {course}", json.dumps(entry, ensure_ascii=False, indent=2))
#                 else:
#                     data['waiting_list'].append(entry)
#                     success_msg = f"הקורס מלא, נרשמת בהצלחה לרשימת המתנה לקורס '{course}' ({ 'קבוצה קטנה' if group_type == 'small' else 'קבוצה רגילה' } )."
#                     email_body = f"""

#                     שם ההורה: {entry['parent_name']} {entry['parent_surname']}
#                     אימייל: {entry['email']}
#                     טלפון: {entry['phone']}

#                     שם הילד/ה: {entry['child_name']}
#                     גיל: {entry['child_age']}
#                     מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}

#                     קורס: {entry['course']}
#                     קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}
#                     """

#                     # אם יש שדות נוספים כמו ביטוח/התחייבות – נוסיף
#                     if "insurance" in entry:
#                         email_body += f"\nקופת חולים: {entry['insurance']}"
#                         email_body += f"\nהתחייבויות: {entry.get('commitments','לא')}"

#                     send_email(f"רשימת המתנה - קורס {course}", email_body)
#                     # send_email(f"רשימת המתנה - קורס {course}", json.dumps(entry, ensure_ascii=False, indent=2))

#                 save_json(REGISTRATIONS_FILE, data)
                

#     # עדכון סטטוס קורסים עבור JS
#     for gender, gender_courses in courses.items():
#         for course_name, groups in gender_courses.items():
#             course_status[course_name] = {}
#             for g_type, info in groups.items():
#                 if info["capacity"] == 0:
#                     course_status[course_name][g_type] = False
#                 else:
#                     count = sum(
#                         1 for r in data['registered']
#                         if r['course'] == course_name and r['group_type'] == g_type
#                     )
#                     course_status[course_name][g_type] = count < info["capacity"]
                
#     if success_msg:
#         flash(success_msg, 'success')
#         return redirect(url_for('register'))
#     elif error_msg:
#         flash(error_msg, 'error')
#         return redirect(url_for('register'))

    
#     prices = load_json('prices.json', {"small": 350, "regular": 280})
#     return render_template(
#         'register.html',
#         courses=courses,
#         course_status=course_status,
#         prices=prices
#     )
   
@app.route('/', methods=['GET','POST'])
def register():
    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})
    data.setdefault('registered', [])
    data.setdefault('waiting_list', [])
    courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})

    prices = load_json('prices.json', {"small": 350, "regular": 280, "months": 5, "registration_active": True})
    
    # וידוא שיש שדה registration_active
    if 'registration_active' not in prices:
        prices['registration_active'] = True
        save_json('prices.json', prices)
    
    registration_active = prices.get('registration_active', True)
    
    error_msg = None
    success_msg = None
    course_status = {}
    
    if request.method == 'POST':

        if not registration_active:
            error_msg = "הרישום לקורסים סגור כרגע. נשמח לראותך בפעם הבאה!"
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        if request.form.get('privacy') != 'accepted':
            flash("חובה לאשר את מדיניות הפרטיות", "error")
            return redirect(url_for('register'))
        # קבלת הנתונים הבסיסיים

        parent_name = request.form.get('parent_name', '').strip()
        parent_surname = request.form.get('parent_surname', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        child_name = request.form.get('child_name', '').strip()
        child_age_str = request.form.get('child_age', '').strip()
        child_gender = request.form.get('child_gender', '').strip()
        course = request.form.get('course', '').strip()
        group_type = request.form.get('group_type', '').strip()
        
        # תחילה - בדיקה בסיסית של השדות החובה לפני הכל
        if not all([parent_name, parent_surname, email, phone, child_name, child_age_str, child_gender, course, group_type]):
            error_msg = "אנא מלא/י את כל השדות החובה."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        # בדיקת גיל תקין
        try:
            child_age = int(child_age_str)
            if child_age < 6 or child_age > 13:
                error_msg = "גיל הילד/ה חייב להיות בין 6 ל-13."
                flash(error_msg, 'error')
                return redirect(url_for('register'))
        except (ValueError, TypeError):
            error_msg = "אנא הכנס גיל תקין במספרים."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        # בדיקות פורמט - טלפון
        phone_pattern = re.compile(r'^(?:\+972|0)(?:5\d\d{7}|[23489]\d{7})$')
        if not phone_pattern.match(phone):
            error_msg = "מספר טלפון לא חוקי. אנא הכנס מספר תקין, לדוגמה נייד 0521234567 או קו בית 03-1234567"
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        # בדיקת אימייל
        if not validate_email(email):
            error_msg = "האימייל אינו חוקי. יש להכניס כתובת אימייל תקינה."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        # בדיקת שמות בעברית
        if not validate_name(parent_name):
            error_msg = "שם ההורה אינו חוקי. יש להשתמש רק באותיות בעברית."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        if not validate_name(parent_surname):
            error_msg = "שם המשפחה אינו חוקי. יש להשתמש רק באותיות בעברית."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        if not validate_name(child_name):
            error_msg = "שם הילד/ה אינו חוקי. יש להשתמש רק באותיות בעברית."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        # בדיקה שהקורס והקבוצה קיימים
        if child_gender not in courses or course not in courses[child_gender] or group_type not in courses[child_gender][course]:
            error_msg = "בחירת הקורס או הקבוצה אינה תקינה."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        # בדיקת גיל מתאים לקבוצה
        age_range = courses[child_gender][course][group_type]["age_range"]
        if not (age_range[0] <= child_age <= age_range[1]):
            error_msg = f"הגיל של הילד/ה לא מתאים ל{ 'קבוצה קטנה' if group_type == 'small' else 'קבוצה רגילה' } (טווח גילאים: {age_range[0]}-{age_range[1]})."
            flash(error_msg, 'error')
            return redirect(url_for('register'))
        
        # אם הגענו עד לכאן - כל הבדיקות הבסיסיות עברו בהצלחה!
        # עכשיו נבדוק אם יש מקום בקורס ונטפל בתשלום
        
        # חישוב אם הקורס מלא
        max_spots = courses[child_gender][course][group_type]["capacity"]
        current_count = sum(
            1 for r in data['registered'] 
            if r['course'] == course and r['group_type'] == group_type
        )
        is_full = current_count >= max_spots
        
        # יצירת רשומה בסיסית
        entry = {
            "parent_name": parent_name,
            "parent_surname": parent_surname,
            "email": email,
            "phone": phone,
            "child_name": child_name,
            "child_age": child_age,
            "child_gender": child_gender,
            "course": course,
            "group_type": group_type
        }
        
        # טיפול בתשלום - רק אם יש מקום בקורס
        if not is_full:
            # בדיקה שקיבלנו פרטי תשלום (זה אומר שהמשתמש עבר דרך חלונית התשלום)
            payment_type = request.form.get("payment_type")
            
            if not payment_type:
                error_msg = "שגיאה: לא נבחר סוג תשלום. אנא נסה שוב."
                flash(error_msg, 'error')
                return redirect(url_for('register'))
            
            # טיפול בתשלום דרך ביטוח
            if payment_type == "insurance":
                insurance = request.form.get("insurance")
                if not insurance:
                    error_msg = "שגיאה: לא נבחרה קופת חולים. אנא בחר קופת חולים."
                    flash(error_msg, 'error')
                    return redirect(url_for('register'))
                
                commitments = "לא"  # ברירת מחדל
                entry["insurance"] = insurance
                entry["commitments"] = commitments
            
            # חישוב סכום לתשלום
            prices = load_json('prices.json', {"small": 350, "regular": 280, "months": 5})
            
            if payment_type == "insurance":
                amount_to_pay = 100
            else:
                if group_type == "small":
                    amount_to_pay = prices["small"] * prices.get("months", 1)
                else:
                    amount_to_pay = prices["regular"] * prices.get("months", 1)
            
            # entry["amount_to_pay"] = amount_to_pay
            
            # # return redirect(payment_url)
            # session["pending_entry"] = entry

            
            # # 3) אם עמוד הסליקה שלך תומך בפרמטר סכום ב-URL, אפשר לצרף אותו כך:
            # #    אין באפשרותי לאשר את שם הפרמטר המדויק. אם לא עובד, השאירי בלי פרמטר והסכום יוגדר בעמוד עצמו.
            # checkout_url = "https://app.icount.co.il/m/8eb31/cd16ap5du68f109677e?utm_source=iCount&utm_medium=paypage&utm_campaign=93" # למשל: f"{ICOUNT_CHECKOUT_URL}?sum={amount_to_pay}"

            # return redirect(checkout_url)
            # מזהה הזמנה ייחודי כדי לשייך בין הסליקה לבין ההזמנה
            order_ref = str(uuid.uuid4())
            entry["order_ref"] = order_ref
            entry["amount_to_pay"] = amount_to_pay

            # נשמור ב-pending (לא תלוי session)
            pending = load_pending()
            pending[order_ref] = entry
            save_pending(pending)

            # נשמור גם ב-session כתמיכה משנית לחזרה דרך הדפדפן
            session["pending_entry"] = entry
            if payment_type == "insurance":
                ICOUNT_CHECKOUT_URL=os.getenv("ICOUNT_CHECKOUT_URL", "https://app.icount.co.il/m/62b62/cd16ap6au6956c4ee7e?utm_source=iCount&utm_medium=paypage&utm_campaign=106")
            elif group_type == "small":           
                ICOUNT_CHECKOUT_URL = os.getenv("ICOUNT_CHECKOUT_URL", "https://app.icount.co.il/m/8eb31/cd16ap5du68f109677e?utm_source=iCount&utm_medium=paypage&utm_campaign=93")
            else:
                ICOUNT_CHECKOUT_URL = os.getenv("ICOUNT_CHECKOUT_URL", "https://app.icount.co.il/m/6e4a9/cd16ap65u6956c51a18?utm_source=iCount&utm_medium=paypage&utm_campaign=101")
            # ננסה להעביר את מזהה ההזמנה כפרמטר. ברוב עמודי הסליקה הפרמטר more חוזר ב-URL תגובות וב-IPN.
            checkout_url = f"{ICOUNT_CHECKOUT_URL}?more={order_ref}"

            return redirect(checkout_url)

            
            # הוספה לרשימת הרשומים
            data['registered'].append(entry)
            success_msg = f"ההרשמה שלך לקורס '{course}' ({ 'קבוצה קטנה' if group_type == 'small' else 'קבוצה רגילה' } ) התקבלה בהצלחה!"
            
            # הכנת תוכן האימייל
            email_body = f"""
שם ההורה: {entry['parent_name']} {entry['parent_surname']}
אימייל: {entry['email']}
טלפון: {entry['phone']}
שם הילד/ה: {entry['child_name']}
גיל: {entry['child_age']}
מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}
קורס: {entry['course']}
קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}
סכום לתשלום: {entry['amount_to_pay']} ש"ח
"""
            
            # אם יש שדות נוספים כמו ביטוח/התחייבות – נוסיף
            if "insurance" in entry:
                email_body += f"\nקופת חולים: {entry['insurance']}"
                email_body += f"\nהתחייבויות: {entry.get('commitments','לא')}"
            
            send_email(f"רישום חדש לקורס {course}", email_body)
            
        else:
            # הקורס מלא - הוספה לרשימת המתנה
            # כאן לא צריך פרטי תשלום כי זה רק רשימת המתנה
            data['waiting_list'].append(entry)
            success_msg = f"הקורס מלא, נרשמת בהצלחה לרשימת המתנה לקורס '{course}' ({ 'קבוצה קטנה' if group_type == 'small' else 'קבוצה רגילה' } )."
            
            # הכנת תוכן האימייל לרשימת המתנה
            email_body = f"""
שם ההורה: {entry['parent_name']} {entry['parent_surname']}
אימייל: {entry['email']}
טלפון: {entry['phone']}
שם הילד/ה: {entry['child_name']}
גיל: {entry['child_age']}
מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}
קורס: {entry['course']}
קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}
"""
            
            send_email(f"רשימת המתנה - קורס {course}", email_body)
        
        # שמירה לקובץ
        save_json(REGISTRATIONS_FILE, data)
        
        # הודעת הצלחה והפנייה
        flash(success_msg, 'success')
        return redirect(url_for('register'))
    
    # עדכון סטטוס קורסים עבור JS (רק ב-GET או אחרי טיפול בשגיאות)
    for gender, gender_courses in courses.items():
        for course_name, groups in gender_courses.items():
            course_status[course_name] = {}
            for g_type, info in groups.items():
                if info["capacity"] == 0:
                    course_status[course_name][g_type] = False
                else:
                    count = sum(
                        1 for r in data['registered'] 
                        if r['course'] == course_name and r['group_type'] == g_type
                    )
                    course_status[course_name][g_type] = count < info["capacity"]
    
    prices = load_json('prices.json',{"small": 350, "regular": 280 ,"months": 5})
    return render_template(
        'register.html',
         registration_active=registration_active,
        courses=courses,
        course_status=course_status,
        prices=prices
    )


app.secret_key = "my_super_secret_key_12345"  

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

FAILED_LOGINS = {}
MAX_ATTEMPTS = 3
LOCK_TIME = 60 * 30   # חצי שעה חסימה

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    error_msg = None
    user_ip = request.remote_addr

    # בדיקה אם המשתמש חסום כרגע
    if user_ip in FAILED_LOGINS:
        attempts, lock_until = FAILED_LOGINS[user_ip]
        if attempts >= MAX_ATTEMPTS and time.time() < lock_until:
            remaining = int(lock_until - time.time())
            error_msg = f"הגישה נחסמה עקב ריבוי ניסיונות שגויים. ניתן לנסות שוב בעוד {remaining} שניות."
            return render_template('admin_login.html', error_msg=error_msg)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # ניקוי ספירת ניסיונות
            if user_ip in FAILED_LOGINS:
                del FAILED_LOGINS[user_ip]

            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))

        # התחברות נכשלה
        if user_ip not in FAILED_LOGINS:
            FAILED_LOGINS[user_ip] = [1, 0]
        else:
            FAILED_LOGINS[user_ip][0] += 1

        attempts = FAILED_LOGINS[user_ip][0]

        if attempts >= MAX_ATTEMPTS:
            FAILED_LOGINS[user_ip][1] = time.time() + LOCK_TIME
            error_msg = "עקב 3 ניסיונות כושלים, הגישה נחסמה  ."
        else:
            error_msg = f"שם משתמש או סיסמה שגויים. נשארו לך {MAX_ATTEMPTS - attempts} ניסיונות."

    return render_template('admin_login.html', error_msg=error_msg)
# @app.route('/admin_login', methods=['GET', 'POST'])
# def admin_login():
#     error_msg = None
#     if request.method == 'POST':
#         username = request.form.get('username')
#         password = request.form.get('password')
#         if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
#             session['admin_logged_in'] = True
#             return redirect(url_for('admin_dashboard'))
#         else:
#             error_msg = "שם משתמש או סיסמה שגויים."
#     return render_template('admin_login.html', error_msg=error_msg)

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    # כאן תכניסי את כל המידע שהמנהל יכול לראות
    return admin_panel()

def admin_panel():
    # courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})
    # prices = load_prices()
    # return render_template("admin_panel.html", courses=courses, prices=prices)
    courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})
    prices = load_json('prices.json', {"small": 350, "regular": 280, "months": 5, "registration_active": True})
    
    # וידוא שיש שדה registration_active
    if 'registration_active' not in prices:
        prices['registration_active'] = True
        save_json('prices.json', prices)
    
    registration_active = prices.get('registration_active', True)
    
    return render_template(
        'admin_panel.html', 
        courses=courses, 
        prices=prices,
        registration_active=registration_active
    )


@app.route('/update_capacity', methods=['POST'])
def update_capacity():
    gender = request.form.get("gender")
    course = request.form.get("course")
    group_type = request.form.get("group_type")
    new_capacity = int(request.form.get("capacity"))

    courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})
    courses[gender][course][group_type]["capacity"] = new_capacity
    save_json(COURSES_FILE, courses)
    flash("קיבולת הקורס עודכנה בהצלחה!", "success")

    return admin_panel()

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('register'))

@app.route('/view_registrations')
def view_registrations():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    gender = request.args.get("gender")
    course = request.args.get("course")
    group_type = request.args.get("group_type")
    
    # הוסף הדפסה לבדיקה
    print("gender מתקבל:", repr(gender))
    print("course מתקבל:", repr(course))
    print("group_type מתקבל:", repr(group_type))
    
    # וודא שכל הפרמטרים קיימים
    if not gender or not course or not group_type:
        flash("פרמטרים חסרים", "error")
        return redirect(url_for('admin_dashboard'))
    
    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})

    # סינון הרשומים והרשימת המתנה לפי הקורס והקבוצה
    registered_list = [
        r for r in data['registered']
        if r['course'] == course and r['group_type'] == group_type
    ]
    waiting_list = [
        r for r in data['waiting_list']
        if r['course'] == course and r['group_type'] == group_type
    ]

    return render_template(
        "view_registrations.html",
        gender=gender,
        course=course,
        group_type=group_type,
        registered_list=registered_list,
        waiting_list=waiting_list
    )


@app.route("/payment_success", methods=["POST"])
def payment_success():
    print("ICOUNT IPN RECEIVED:", dict(request.values))

    order_ref = (
        request.values.get("more")
        or request.values.get("reference")
        or _extract_more_from_utm(request.values.get("utm_campaign"))
    )

    if not order_ref:
        return "missing reference", 400

    pending = load_pending()
    entry = pending.pop(order_ref, None)
    save_pending(pending)

    if not entry:
        return "not found", 200   # חשוב לא להחזיר שגיאה

    entry["payment_status"] = "שולם"

    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})
    data["registered"].append(entry)
    save_json(REGISTRATIONS_FILE, data)

    email_body = f"""
שם ההורה: {entry['parent_name']} {entry['parent_surname']}
אימייל: {entry['email']}
טלפון: {entry['phone']}
שם הילד/ה: {entry['child_name']}
גיל: {entry['child_age']}
מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}
קורס: {entry['course']}
קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}
סכום לתשלום: {entry['amount_to_pay']} ש"ח
"""
    if "insurance" in entry:
        email_body += f"\nקופת חולים: {entry['insurance']}"
        email_body += f"\nהתחייבויות: {entry.get('commitments','לא')}"

    send_email("רישום חדש לקורס", email_body)

    return "OK", 200

@app.route("/payment_fail")
def payment_fail():
    flash("התשלום נכשל או בוטל. אנא נסה שוב.", "error")
    return redirect(url_for('register'))


@app.route('/cancel_registration', methods=['POST'])
def cancel_registration():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    email = request.form.get("email")
    child_name = request.form.get("child_name")
    course = request.form.get("course")
    group_type = request.form.get("group_type")
    list_type = request.form.get("list_type")  # registered / waiting_list
    gender = request.form.get("gender")  # חשוב!
    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})
    
    # מסנן החוצה את הנרשם שרוצים למחוק
    data[list_type] = [
        r for r in data[list_type]
        if not (r["email"] == email and r["child_name"] == child_name and r["course"] == course and r["group_type"] == group_type)
    ]

    save_json(REGISTRATIONS_FILE, data)

    # חזרה לעמוד הרשומים של אותו קורס
    return redirect(url_for(
        'view_registrations',
        gender=gender,
        course=course,
        group_type=group_type
    ))


@app.route('/export_registrations_xlsx')
def export_registrations_xlsx():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})

    # יצירת workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "נרשמים"

    # כותרות
    headers = ["שם ההורה", "שם משפחה", "אימייל", "טלפון",
               "שם הילד/ה", "גיל", "מגדר", "קורס", "קבוצה"]
    ws.append(headers)

    # מילוי הנתונים
    for r in data['registered']:
        ws.append([
            r["parent_name"],
            r["parent_surname"],
            r["email"],
            r["phone"],
            r["child_name"],
            r["child_age"],
            "בן" if r["child_gender"]=="boys" else "בת",
            r["course"],
            "קבוצה קטנה" if r["group_type"]=="small" else "קבוצה רגילה"
        ])

    # שמירה בזיכרון כדי לשלוח כקובץ
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
    output,
    download_name="נרשמים.xlsx",
    as_attachment=True,
    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@app.route('/add_course', methods=['POST'])
def add_course():
    course_name = request.form['course_name']
    gender = request.form['gender']

    # טווחים וקיבולות של שתי הקבוצות
    small_capacity = int(request.form['small_capacity'])
    small_age_range = [int(x) for x in request.form['small_age_range'].split('-')]

    regular_capacity = int(request.form['regular_capacity'])
    regular_age_range = [int(x) for x in request.form['regular_age_range'].split('-')]

    # מיפוי מגדר
    gender_map = {
        "בנים": "boys",
        "בנות": "girls"
    }
    gender_key = gender_map.get(gender)
    if not gender_key:
        flash("שגיאה: מין לא חוקי")
        return redirect(url_for('admin_dashboard'))

    # טוענים JSON
    courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})

    # אם אין עדיין קורס כזה – נוסיף
    if course_name not in courses[gender_key]:
        courses[gender_key][course_name] = {}

    # שמירה של שתי הקבוצות
    courses[gender_key][course_name]['small'] = {
        "capacity": small_capacity,
        "age_range": small_age_range
    }
    courses[gender_key][course_name]['regular'] = {
        "capacity": regular_capacity,
        "age_range": regular_age_range
    }

    save_json(COURSES_FILE, courses)
    flash("הקורס נוסף בהצלחה עם שתי הקבוצות!", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/add_registrant/<gender>/<course>/<group_type>', methods=['POST'])
def add_registrant(gender, course, group_type):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})
    courses = load_json(COURSES_FILE, {"boys": {}, "girls": {}})
    print("gende before",gender)
    # מיפוי מגדר לעברית ול-json
    # gender_key = "boys" if gender == "בן" else "girls"
    
    # קבלת שדות מהטופס
    parent_name = request.form.get('parent_name')
    parent_surname = request.form.get('parent_surname')
    email = request.form.get('email')
    phone = request.form.get('phone')
    child_name = request.form.get('child_name')
    child_age = int(request.form.get('child_age'))

    # בדיקה אם כל השדות מלאים
    if not all([parent_name, parent_surname, email, phone, child_name, child_age]):
        flash("אנא מלא/י את כל השדות.", "error")
        return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))
    
    # print(course_n)
    group_type = "small" if group_type in ["small", "קטנה"] else "regular"

    print("gender",gender)
    print("group",group_type)
    # בדיקת טווח גילאים
    age_range = courses[gender][course][group_type]["age_range"]
    if not (age_range[0] <= child_age <= age_range[1]):
        flash(f"הגיל של הילד/ה לא מתאים לקורס (טווח גילאים: {age_range[0]}-{age_range[1]}).", "error")
        return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))
    print(gender)
    # בדיקה אם הקורס מלא
    max_spots = courses[gender][course][group_type]["capacity"]
    current_count = sum(
        1 for r in data['registered']
        if r['course'] == course and r['group_type'] == group_type
    )
    is_full = current_count >= max_spots

    entry = {
        "parent_name": parent_name,
        "parent_surname": parent_surname,
        "email": email,
        "phone": phone,
        "child_name": child_name,
        "child_age": child_age,
        "child_gender": gender,  # לשמירה עקבית ב-json
        "course": course,
        "group_type": group_type
    }

    if not is_full:
        data['registered'].append(entry)
        flash(f"ההרשמה של {child_name} התקבלה בהצלחה!", "success")
        email_body = f"""
        שם ההורה: {entry['parent_name']} {entry['parent_surname']}
        אימייל: {entry['email']}
        טלפון: {entry['phone']}
        שם הילד/ה: {entry['child_name']}
        גיל: {entry['child_age']}
        מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}
        קורס: {entry['course']}
        קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}

        """
            
           
        # אם יש שדות נוספים כמו ביטוח/התחייבות – נוסיף
        # if "insurance" in entry:
        #     email_body += f"\nקופת חולים: {entry['insurance']}"
        #     email_body += f"\nהתחייבויות: {entry.get('commitments','לא')}"

        send_email(f"רישום חדש לקורס {course}", email_body)
        
        # send_email(f"רישום חדש לקורס {course}", json.dumps(entry, ensure_ascii=False, indent=2))
    else:
        data['waiting_list'].append(entry)
        flash(f"הקורס מלא, {child_name} נוסף/ה לרשימת המתנה.", "success")
        email_body = f"""
        שם ההורה: {entry['parent_name']} {entry['parent_surname']}
        אימייל: {entry['email']}
        טלפון: {entry['phone']}
        שם הילד/ה: {entry['child_name']}
        גיל: {entry['child_age']}
        מגדר: {"בן" if entry['child_gender']=="boys" else "בת"}
        קורס: {entry['course']}
        קבוצה: {"קבוצה קטנה" if entry['group_type']=="small" else "קבוצה רגילה"}
        """


        send_email(f"רשימת המתנה - קורס {course}", email_body)
        # send_email(f"רשימת המתנה - קורס {course}", json.dumps(entry, ensure_ascii=False, indent=2))

    save_json(REGISTRATIONS_FILE, data)
    return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))


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

@app.route('/update_prices', methods=['POST'])
def update_prices():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    small_price = request.form.get("small_price")
    regular_price = request.form.get("regular_price")
    months = request.form.get("months")

    if not small_price or not regular_price:
        flash("יש למלא את כל השדות", "error")
        return redirect(url_for('admin_dashboard'))

    prices = {"small": int(small_price), "regular": int(regular_price),"months": int(months)}
    save_prices(prices)
    flash("מחירי הקורסים עודכנו בהצלחה", "success")
    return redirect(url_for('admin_dashboard'))

@app.route("/toggle_commitment", methods=["POST"])
def toggle_commitment():
    email = request.form["email"]
    child_name = request.form["child_name"]
    course = request.form["course"]
    group_type = request.form["group_type"]
    gender = request.form["gender"]

    data = load_json(REGISTRATIONS_FILE, {"registered": []})  # טוען את הקובץ JSON עם כל הנרשמים

    # חיפוש נרשם מתאים ברשימה
    updated = False
    for lst in ["registered", "waiting_list"]:
        for r in data.get(lst, []):
            if (
                r["email"] == email
                and r["child_name"] == child_name
                and r["course"] == course
                and r["group_type"] == group_type
            ):
                if r.get("commitments") == "כן":
                    r["commitments"] = "לא"
                else:
                    r["commitments"] = "כן"
                updated = True
                break
        if updated:
            break

    if updated:
        save_json(REGISTRATIONS_FILE, data)

    # flash("סטטוס התחייבות עודכן בהצלחה", "success")
    return redirect(url_for("view_registrations", gender=gender, course=course, group_type=group_type))


# פונקציה להפסקת/חידוש רישום
@app.route('/toggle_registration', methods=['POST'])

def toggle_registration():
    """מחליף את סטטוס הרישום בין פעיל ללא פעיל"""
    prices = load_json('prices.json', {"small": 350, "regular": 280, "months": 5, "registration_active": True})
    
    # הפיכת הסטטוס
    current_status = prices.get('registration_active', True)
    prices['registration_active'] = not current_status
    
    save_json('prices.json', prices)
    
    # הודעת משוב למנהל
    if prices['registration_active']:
        flash('הרישום חודש בהצלחה! משתמשים יכולים כעת להירשם לקורסים.', 'success')
    else:
        flash('הרישום הופסק בהצלחה. משתמשים לא יכולים להירשם כרגע.', 'success')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/charge_token', methods=['POST'])
def charge_token():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    email = request.form.get("email")
    child_name = request.form.get("child_name")
    course = request.form.get("course")
    group_type = request.form.get("group_type")
    gender = request.form.get("gender")
    amount = float(request.form.get("amount"))
    description = request.form.get("description") or "תשלום נוסף"

    data = load_json(REGISTRATIONS_FILE, {"registered": [], "waiting_list": []})
    registrant = next((r for r in data["registered"]
                       if r["email"] == email and r["child_name"] == child_name and
                          r["course"] == course and r["group_type"] == group_type), None)

    if not registrant:
        flash("לא נמצאה הרשומה לתשלום חוזר", "error")
        return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))

    token = (registrant.get("icount", {}) or {}).get("card_token") or registrant.get("card_token")
    if not token:
        flash("לא נמצא טוקן שמור לכרטיס האשראי", "error")
        return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))

    payload = {
        "cid": ICOUNT_CID,
        "user": ICOUNT_USER,
        "pass": ICOUNT_PASS,
        "cc_token": token,
        "sum": amount,
        "currency_code": "ILS",
        "description": description,
        "doctype": "receipt",
        "email_client": 0
    }

    try:
        res = requests.post("https://api.icount.co.il/api/v3.php/pay/bytoken", data=payload, timeout=20)
        response_data = res.json()
        if not response_data.get("status"):
            flash(f"שגיאה בחיוב: {response_data.get('error_description', 'לא ידועה')}", "error")
            return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))
    except Exception as e:
        flash(f"שגיאה בחיבור ל-iCount: {str(e)}", "error")
        return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))

    # שמירת פרטי החיוב
    registrant.setdefault("extra_payments", []).append({
        "amount": amount,
        "description": description,
        "timestamp": datetime.now().isoformat(),
        "docnum": response_data.get("docnum"),
        "confirmation_code": response_data.get("confirmation_code")
    })
    save_json(REGISTRATIONS_FILE, data)

    flash("החיוב בוצע בהצלחה!", "success")
    return redirect(url_for('view_registrations', gender=gender, course=course, group_type=group_type))

if __name__ == '__main__':
    app.run(debug=True)
