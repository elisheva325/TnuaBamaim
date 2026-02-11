from time import time
from flask import session, redirect, url_for
from flask import flash
from openpyxl import Workbook
from flask import send_file
import io
import requests
from flask import Flask, render_template, request
import json, os, smtplib
from flask_sqlalchemy import SQLAlchemy
from email.mime.text import MIMEText
import re
import uuid
from typing import Dict
from urllib.parse import parse_qs
import requests
from dotenv import load_dotenv
from decimal import Decimal
load_dotenv()
app = Flask(__name__)

app.secret_key = "my_super_secret_key_12345" 
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "postgresql://postgres.xjlhtghkdypuldvcutjd:yzQ-2rtM!Agjp?A@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy()          # ← בלי app כאן
db.init_app(app)  
print("DB ID FROM APP:", id(db))


from functions import *

@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html")

# @app.route('/', methods=['GET','POST'])
# def register():

#     active = load_json('prices.json', { "registration_active": True})

#     registration_active = active.get("registration_active", True )
#     prices = load_prices_from_db(db)

#     if not prices:
#         flash("שגיאה בטעינת מחירים.", "error")
#         return redirect(url_for('register'))
#     if request.method == 'POST':

#         if not registration_active:
#             flash("הרישום סגור כרגע.", "error")
#             return redirect(url_for('register'))

#         if request.form.get('privacy') != 'accepted':
#             flash("יש לאשר מדיניות פרטיות.", "error")
#             return redirect(url_for('register'))

#         parent_name = request.form.get('parent_name','').strip()
#         parent_surname = request.form.get('parent_surname','').strip()
#         email = request.form.get('email','').strip()
#         phone = request.form.get('phone','').strip()
#         child_name = request.form.get('child_name','').strip()
#         child_age_str = request.form.get('child_age','').strip()
#         child_gender = request.form.get('child_gender','').strip()
#         course = request.form.get('course','').strip()
#         group_type = request.form.get('group_type','').strip()
#         id=request.form.get('id','').strip()

#         if not all([parent_name, parent_surname, email, phone, child_name, child_age_str, child_gender, course, group_type]):
#             flash("יש למלא את כל השדות.", "error")
#             return redirect(url_for('register'))

#         try:
#             child_age = int(child_age_str)
#         except:
#             flash("יש להזין גיל במספרים בלבד.", "error")
#             return redirect(url_for('register'))

#         group = get_course_group(db, child_gender, course, group_type)

#         if not group:
#             flash("בחירת הקורס אינה תקינה.", "error")
#             return redirect(url_for('register'))

#         if not (group["min_age"] <= child_age <= group["max_age"]):
#             flash(f"הגיל אינו מתאים (טווח {group['min_age']}-{group['max_age']}).", "error")
#             return redirect(url_for('register'))

#         current_count = db.session.execute(
#             db.text("""
#                 select count(*)
#                 from registrations
#                 where course_group_id = :gid
#                   and status = 'registered'
#             """),
#             {"gid": group["id"]}
#         ).scalar()

#         is_full = current_count >= group["capacity"]

#         payment_type = request.form.get("payment_type")
        
#         if not payment_type and not is_full:
#             flash("לא נבחר סוג תשלום.", "error")
#             return redirect(url_for('register'))

#         if payment_type == "insurance":
#             amount_to_pay = 100
#         else:
#             if group_type == "small":
#                 base = prices["small"]
#             else:
#                 base = prices["regular"]

#             months = prices.get("months", 1)
#             amount_to_pay = base * months

#         order_ref = str(uuid.uuid4())
#         pending_entry = {
         
#             "course": course,           # חסר! פונקציית add_registrant_db חייבת את זה
#             "group_type": group_type,
#             "parent_name": parent_name,
#             "parent_surname": parent_surname,
#             "email": email,
#             "phone": phone,
#             "child_name": child_name,
#             "child_age": child_age,
#             "child_gender": child_gender,
#             "id_number": id,
#             "order_ref": order_ref,
#         }

#         # session["pending_entry"] = pending_entry


#         if is_full:
#             # אין תשלום לרשימת המתנה
#             send_email(
#                 f"רשימת המתנה - קורס {course}",
#                 f"""
#                 שם ההורה: {parent_name} {parent_surname}
#                 טלפון: {phone}
#                 אימייל: {email}
#                 שם הילד/ה: {child_name}
#                 גיל: {child_age}
#                 קורס: {course}
#                 קבוצה: {"קבוצה קטנה" if group_type=="small" else "קבוצה רגילה"}
#                 """
#             )

#             flash("הקורס מלא. נרשמת לרשימת המתנה.", "success")

#             # הכנסת רשימת המתנה תתבצע ב-success ראוט
#             return redirect(url_for('register'))

#         else:
#             # רישום רגיל – ממשיכים לתשלום
#             # send_email(
#             #     f"התחלת רישום לקורס {course}",
#             #     f"""
#             #     שם ההורה: {parent_name} {parent_surname}
#             #     טלפון: {phone}
#             #     אימייל: {email}
#             #     שם הילד/ה: {child_name}
#             #     סכום לתשלום: {amount_to_pay} ש"ח
#             #     """
#             # )
            

#             if payment_type == "insurance":
#                 ICOUNT_CHECKOUT_URL=os.getenv("ICOUNT_CHECKOUT_URL", "https://app.icount.co.il/m/62b62/cd16ap6au6956c4ee7e?utm_source=iCount&utm_medium=paypage&utm_campaign=106")
#             elif group_type == "small":           
#                 ICOUNT_CHECKOUT_URL = os.getenv("ICOUNT_CHECKOUT_URL", "https://app.icount.co.il/m/8eb31/cd16ap5du68f109677e?utm_source=iCount&utm_medium=paypage&utm_campaign=93")
#             else:
#                 ICOUNT_CHECKOUT_URL = os.getenv("ICOUNT_CHECKOUT_URL", "https://app.icount.co.il/m/6e4a9/cd16ap65u6956c51a18?utm_source=iCount&utm_medium=paypage&utm_campaign=101")
#             checkout_url = f"{ICOUNT_CHECKOUT_URL}?more={order_ref}"

#             pending = load_json("pending.json", {})
#             pending[order_ref] = pending_entry
#             save_json("pending.json", pending)

#             return redirect(checkout_url)

#             # if payment_type == "insurance":
#             #     checkout_url = os.getenv("ICOUNT_INSURANCE_URL")
#             # elif group_type == "small":
#             #     checkout_url = os.getenv("ICOUNT_SMALL_URL")
#             # else:
#             #     checkout_url = os.getenv("ICOUNT_REGULAR_URL")
           
#             # print("FINAL CHECKOUT URL:", f"{checkout_url}?more={order_ref}")
#             # return redirect(f"{checkout_url}?more={order_ref}")

#     # GET
#     courses = load_courses_from_db(db)
#     course_status = calculate_course_status(db)

#     return render_template(
#         "register.html",
#         registration_active=registration_active,
#         courses=courses,
#         course_status=course_status,
#         prices=prices
#     )

@app.route('/', methods=['GET','POST'])
def register():
    active = load_json('prices.json', { "registration_active": True})
    registration_active = active.get("registration_active", True )
    
    raw_prices = load_prices_from_db(db)
    if not raw_prices:
        flash("שגיאה בטעינת מחירים.", "error")
        return redirect(url_for('register'))
    
    # המרה ל-float רק בשביל ה-JS (כדי למנוע את שגיאת ה-Decimal)
    prices = {k: float(v) if isinstance(v, Decimal) else v for k, v in raw_prices.items()}

    if request.method == 'POST':
        if not registration_active:
            flash("הרישום סגור כרגע.", "error")
            return redirect(url_for('register'))

        if request.form.get('privacy') != 'accepted':
            flash("יש לאשר מדיניות פרטיות.", "error")
            return redirect(url_for('register'))

        # שליפת הנתונים שלך
        parent_name = request.form.get('parent_name','').strip()
        parent_surname = request.form.get('parent_surname','').strip()
        email = request.form.get('email','').strip()
        phone = request.form.get('phone','').strip()
        child_name = request.form.get('child_name','').strip()
        child_age_str = request.form.get('child_age','').strip()
        child_gender = request.form.get('child_gender','').strip()
        course = request.form.get('course','').strip()
        group_type = request.form.get('group_type','').strip()
        id_val = request.form.get('id','').strip()

        if not all([parent_name, parent_surname, email, phone, child_name, child_age_str, child_gender, course, group_type]):
            flash("יש למלא את כל השדות.", "error")
            return redirect(url_for('register'))
        try:
            child_age = int(child_age_str)
            group = get_course_group(db, child_gender, course, group_type)
            print(f"--- DEBUG REGISTRATION ---")
            print(f"Gender from form: {child_gender}")
            print(f"Course: {course}, Group Type: {group_type}")
            print(f"Age entered: {child_age}")
            print(f"Group found in DB: {group}") # אם זה None, פה הבעיה
            if group:
                print(f"DB Limits: {group['min_age']} to {group['max_age']}")
            print(f"---------------------------")
            if not group or not (group["min_age"] <= child_age <= group["max_age"]):
                flash("הגיל אינו מתאים לקבוצה.", "error")
                return redirect(url_for('register'))
        except:
            flash("נתוני גיל או קבוצה לא תקינים.", "error")
            return redirect(url_for('register'))

        # try:
        #     child_age = int(child_age_str)
        # except:
        #     flash("יש להזין גיל במספרים בלבד.", "error")
        #     return redirect(url_for('register'))

        # group = get_course_group(db, child_gender, course, group_type)
        # if not group:
        #     flash("בחירת הקורס אינה תקינה.", "error")
        #     return redirect(url_for('register'))

        # if not (group["min_age"] <= child_age <= group["max_age"]):
        #     flash(f"הגיל אינו מתאים (טווח {group['min_age']}-{group['max_age']}).", "error")
        #     return redirect(url_for('register'))

        # בדיקת תפוסה
        current_count = db.session.execute(
            db.text("select count(*) from registrations where course_group_id = :gid and status = 'registered'"),
            {"gid": group["id"]}
        ).scalar()

        is_full = current_count >= group["capacity"]
        order_ref = str(uuid.uuid4())

        # בניית ה-Entry
        pending_entry = {
            "course": course,
            "group_type": group_type,
            "parent_name": parent_name,
            "parent_surname": parent_surname,
            "email": email,
            "phone": phone,
            "child_name": child_name,
            "child_age": child_age,
            "child_gender": child_gender,
            "id_number": id_val,
            "order_ref": order_ref,
        }

        # --- התיקון: רישום לרשימת המתנה ---
        if is_full:
            # כאן אנחנו קוראים לפונקציה שלך שמעדכנת את ה-DB בסטטוס 'waiting'
            add_registrant_db(
                db=db,
                gender=child_gender,
                course_name=course,
                group_type=group_type,
                parent_name=parent_name,
                parent_surname=parent_surname,
                email=email,
                phone=phone,
                child_name=child_name,
                child_age=child_age,
                id_number=id_val,
                insurance="", # אין ביטוח ברשימת המתנה
                commitments=False
            )
            
            send_email(f"רשימת המתנה - קורס {course}", f"הילד {child_name} נוסף לרשימת המתנה.")
            flash("הקורס מלא. נרשמת בהצלחה לרשימת המתנה.", "success")
            return redirect(url_for('register'))

        else:
            # מקרה של רישום רגיל - יציאה לתשלום
            payment_type = request.form.get("payment_type")
            if not payment_type:
                flash("לא נבחר סוג תשלום.", "error")
                return redirect(url_for('register'))

            # הקישורים המקוריים שלך
            if payment_type == "insurance":
                ICOUNT_URL = "https://app.icount.co.il/m/62b62/cd16ap6au6956c4ee7e?utm_source=iCount&utm_medium=paypage&utm_campaign=106"
            elif group_type == "small":           
                ICOUNT_URL = "https://app.icount.co.il/m/8eb31/cd16ap5du68f109677e?utm_source=iCount&utm_medium=paypage&utm_campaign=93"
            else:
                ICOUNT_URL = "https://app.icount.co.il/m/6e4a9/cd16ap65u6956c51a18?utm_source=iCount&utm_medium=paypage&utm_campaign=101"
            
            # שמירה ל-pending.json לפני היציאה
            pending = load_json("pending.json", {})
            pending[order_ref] = pending_entry
            save_json("pending.json", pending)

            # חזרה לפורמט המקורי שלך
            return redirect(f"{ICOUNT_URL}?more={order_ref}")

    # GET
    courses = load_courses_from_db(db)
    course_status = calculate_course_status(db)
    return render_template('register.html', registration_active=registration_active, 
                           courses=courses, course_status=course_status, prices=prices)
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

# חדש
@app.route('/admin_dashboard')
def admin_dashboard():
    # if not session.get('admin_logged_in'):
    #     return redirect(url_for('admin_login'))
    # # כאן תכניסי את כל המידע שהמנהל יכול לראות
    # return admin_panel()

    courses = load_courses_from_db(db)
    prices = load_prices_from_db(db)
    active = load_json('prices.json', { "registration_active": True})

    registration_active = active.get("registration_active", True)

    return render_template(
        "admin_panel.html",
        courses=courses,
        prices=prices,
        registration_active=registration_active
    )

# חדש
@app.route('/update_capacity', methods=['POST'])
def update_capacity():
    gender = request.form.get("gender")
    course_name = request.form.get("course")
    group_type = request.form.get("group_type")
    new_capacity = int(request.form.get("capacity"))

    success = update_course_capacity(
        db,
        gender,
        course_name,
        group_type,
        new_capacity,
    )

    if success:
        flash("קיבולת הקורס עודכנה בהצלחה!", "success")
    else:
        flash("לא נמצא קורס מתאים לעדכון.", "danger")

    return redirect(url_for('admin_dashboard'))


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('register'))

# חדש
@app.route('/view_registrations')
def view_registrations():
    # if not session.get('admin_logged_in'):
    #     return redirect(url_for('admin_login'))

    gender = request.args.get("gender")
    course = request.args.get("course")
    group_type = request.args.get("group_type")

    if not gender or not course or not group_type:
        flash("פרמטרים חסרים", "error")
        return redirect(url_for('admin_dashboard'))

    registered_list, waiting_list = get_registrations_for_course(
        db,
        gender,
        course,
        group_type
    )

    return render_template(
        "view_registrations.html",
        gender=gender,
        course=course,
        group_type=group_type,
        registered_list=registered_list,
        waiting_list=waiting_list
    )


def _extract_more_from_utm(val: str):
    if not val:
        return None
    if "?" in val:
        q = val.split("?", 1)[1]
        qs = parse_qs(q)
        m = qs.get("more", [None])[0]
        return m
    return None

# לדש
@app.route("/payment_success", methods=["GET", "POST"], strict_slashes=False)
def payment_success():
    try:
        print("ICOUNT IPN RECEIVED:", dict(request.values))

        order_ref = (
            request.values.get("more")
            or request.values.get("reference")
            or _extract_more_from_utm(request.values.get("utm_campaign"))
        )
        # order_ref = request.values.get("cp")

        print("EXTRACTED ORDER REF:", order_ref)
        if not order_ref:
            return "missing reference", 200  # לא מחזירים 400 ל-IPN

       
        pending = load_json("pending.json", {})
        pending_entry = pending.pop(order_ref, None)

        if not pending_entry:
            return "not found", 200

        if pending_entry.get("order_ref") != order_ref:
            return "mismatch", 200

        status, age_data = add_registrant_db(
            db=db,
            gender=pending_entry["child_gender"],
            course_name=pending_entry["course"],
            group_type=pending_entry["group_type"],
            parent_name=pending_entry["parent_name"],
            parent_surname=pending_entry["parent_surname"],
            email=pending_entry["email"],
            phone=pending_entry["phone"],
            child_name=pending_entry["child_name"],
            child_age=pending_entry["child_age"],
            id_number=pending_entry["id_number"],
            insurance=pending_entry.get("insurance",""),
            commitments=pending_entry.get("commitments", False)
        )

        if status == "registered":

            email_body = f"""
            שם ההורה: {pending_entry['parent_name']} {pending_entry['parent_surname']}
            אימייל: {pending_entry['email']}
            טלפון: {pending_entry['phone']}
            שם הילד/ה: {pending_entry['child_name']}
            גיל: {pending_entry['child_age']}
            קבוצה: {"קבוצה קטנה" if pending_entry['group_type']=="small" else "קבוצה רגילה"}
            """

            send_email("הרשמה הושלמה בהצלחה", email_body)

        # ניקוי session
        session.pop("pending_entry", None)

        return "OK", 200

    except Exception as e:
        print("PAYMENT_SUCCESS ERROR:", e)
        return "OK", 200  # חשוב לא להחזיר 500 ל-iCount


@app.route("/payment_fail")
def payment_fail():
    flash("התשלום נכשל או בוטל. אנא נסה שוב.", "error")
    return redirect(url_for('register'))

# חדש
@app.route('/cancel_registration', methods=['POST'])
def cancel_registration():
    # if not session.get('admin_logged_in'):
    #     return redirect(url_for('admin_login'))

    registration_id = request.form.get("registration_id")
    gender = request.form.get("gender")
    course = request.form.get("course")
    group_type = request.form.get("group_type")

    if not registration_id:
        flash("שגיאה: מזהה רישום חסר", "error")
        return redirect(url_for('admin_dashboard'))

    success = delete_registration(db, registration_id)

    if success:
        flash("הרישום בוטל בהצלחה", "success")
    else:
        flash("הרישום לא נמצא", "error")

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

# חדש
@app.route('/add_course', methods=['POST'])
def add_course():
    print("FORM DATA:", request.form)
    course_name = request.form['course_name']
    gender = request.form['gender']

    small_capacity = int(request.form['small_capacity'])
    regular_capacity = int(request.form['regular_capacity'])

  
    if not gender:
        flash("שגיאה: מין לא חוקי", "danger")
        return redirect(url_for('admin_dashboard'))

    create_course_with_groups(
        db,
        course_name,
        gender,
        small_capacity,
        regular_capacity
    )

    flash("הקורס נוסף בהצלחה עם שתי הקבוצות!", "success")
    return redirect(url_for('admin_dashboard'))

# חדש
@app.route('/add_registrant/<gender>/<course>/<group_type>', methods=['POST'])
def add_registrant(gender, course, group_type):
    # if not session.get('admin_logged_in'):
    #     return redirect(url_for('admin_login'))

    parent_name = request.form.get('parent_name')
    parent_surname = request.form.get('parent_surname')
    email = request.form.get('email')
    phone = request.form.get('phone')
    child_name = request.form.get('child_name')
    child_age = request.form.get('child_age')
    id_number = request.form.get('id_number')
    insurance = request.form.get('insurance')
    commitments_raw = request.form.get('commitments')
    commitments = True if commitments_raw == "true" else False

    if not all([parent_name, parent_surname, email, phone, child_name, child_age, id_number]):
        flash("אנא מלא/י את כל השדות.", "error")
        return redirect(url_for('view_registrations',
                                gender=gender,
                                course=course,
                                group_type=group_type))

    # ולידציית ת"ז בסיסית
    if not id_number.isdigit() or len(id_number) != 9:
        flash("מספר תעודת זהות לא תקין.", "error")
        return redirect(url_for('view_registrations',
                                gender=gender,
                                course=course,
                                group_type=group_type))

    child_age = int(child_age)
    group_type = "small" if group_type in ["small", "קטנה"] else "regular"

    result, extra = add_registrant_db(
        db,
        gender,
        course,
        group_type,
        parent_name,
        parent_surname,
        email,
        phone,
        child_name,
        child_age,
        id_number,
        insurance,
        commitments
    )

    if result == "not_found":
        flash("הקורס לא נמצא.", "error")

    elif result == "age_error":
        min_age, max_age = extra
        flash(f"הגיל לא מתאים לקורס (טווח: {min_age}-{max_age}).", "error")

    elif result == "registered":
        flash(f"ההרשמה של {child_name} התקבלה בהצלחה!", "success")
        send_email(f"רישום חדש לקורס {course}", f"{child_name} נרשם בהצלחה.")

    elif result == "waiting":
        flash(f"הקורס מלא, {child_name} נוסף/ה לרשימת המתנה.", "success")
        send_email(f"רשימת המתנה - קורס {course}", f"{child_name} נוסף לרשימת המתנה.")

    return redirect(url_for('view_registrations',
                            gender=gender,
                            course=course,
                            group_type=group_type))

# חדש
@app.route('/update_prices', methods=['POST'])
def update_prices():
    # if not session.get('admin_logged_in'):
    #     return redirect(url_for('admin_login'))

    small_price = request.form.get("small_price")
    regular_price = request.form.get("regular_price")
    months = request.form.get("months")

    if not small_price or not regular_price or not months:
        flash("יש למלא את כל השדות", "error")
        return redirect(url_for('admin_dashboard'))

    try:
        small_price = int(small_price)
        regular_price = int(regular_price)
        months = int(months)
    except ValueError:
        flash("הערכים חייבים להיות מספריים", "error")
        return redirect(url_for('admin_dashboard'))

    update_course_prices(
        db,
        small_price,
        regular_price,
        months
    )

    flash("מחירי הקורסים עודכנו בהצלחה", "success")
    return redirect(url_for('admin_dashboard'))

# חדש
@app.route("/toggle_commitment", methods=["POST"])
def toggle_commitment():
    registration_id = request.form.get("registration_id")
    gender = request.form.get("gender")
    course = request.form.get("course")
    group_type = request.form.get("group_type")

    if not registration_id:
        flash("שגיאה בעדכון התחייבות", "error")
        return redirect(url_for("admin_dashboard"))

    success = toggle_commitment_db(db, registration_id)

    if not success:
        flash("הרשומה לא נמצאה", "error")

    return redirect(
        url_for(
            "view_registrations",
            gender=gender,
            course=course,
            group_type=group_type
        )
    )


# חדש
@app.route('/toggle_registration', methods=['POST'])
def toggle_registration():
    """מחליף את סטטוס הרישום בין פעיל ללא פעיל"""
    active = load_json('prices.json', { "registration_active": True})
    
    # הפיכת הסטטוס
    current_status = active.get('registration_active', True)
    active['registration_active'] = not current_status
    
    save_json('prices.json', active)
    
    # הודעת משוב למנהל
    if active['registration_active']:
        flash('הרישום חודש בהצלחה! משתמשים יכולים כעת להירשם לקורסים.', 'success')
    else:
        flash('הרישום הופסק בהצלחה. משתמשים לא יכולים להירשם כרגע.', 'success')
    
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
