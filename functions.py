
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


HEBREW_NAME_REGEX = re.compile(r'^[א-ת\s\-]{2,30}$')

def validate_hebrew_name(name):
    return bool(HEBREW_NAME_REGEX.match(name))

def validate_phone(phone):
    phone_pattern = re.compile(r'^(?:\+972|0)(?:5\d{8}|[23489]\d{7})$')
    return bool(phone_pattern.match(phone))

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

def finalize_registration_from_pending(db, entry):

    # בדיקה אם כבר הוכנס
    existing = db.session.execute(
        db.text("""
            select id
            from registrations
            where order_ref = :order_ref
        """),
        {"order_ref": entry["order_ref"]}
    ).first()

    if existing:
        return False  # כבר הוכנס בעבר

    db.session.execute(
        db.text("""
            insert into registrations (
                course_group_id,
                parent_first_name,
                parent_last_name,
                email,
                phone,
                child_first_name,
                child_age,
                child_gender,
                status,
                insurance,
                commitments,
                order_ref,
                payment_status
            )
            values (
                :course_group_id,
                :parent_first_name,
                :parent_last_name,
                :email,
                :phone,
                :child_first_name,
                :child_age,
                :child_gender,
                :status,
                :insurance,
                :commitments,
                :order_ref,
                'שולם'
            )
        """),
        entry
    )

    db.session.commit()
    return True

def calculate_course_status(db):

    rows = db.session.execute(
        db.text("""
            select
                c.course_name,
                ct.name as group_type,
                cg.capacity,
                count(r.id) filter (where r.status = 'registered') as registered_count
            from course_groups cg
            join courses c on c.id = cg.course_id
            join course_types ct on ct.id = cg.course_type_id
            left join registrations r on r.course_group_id = cg.id
            group by c.course_name, ct.name, cg.capacity
        """)
    ).mappings().all()

    result = {}

    for row in rows:
        course_name = row["course_name"]
        group_type = row["group_type"]
        capacity = row["capacity"]
        registered_count = row["registered_count"] or 0

        if course_name not in result:
            result[course_name] = {}

        result[course_name][group_type] = registered_count < capacity

    return result
def get_course_group(db, gender, course_name, group_type):
    return db.session.execute(
        db.text("""
            select
                cg.id,
                cg.capacity,
                ct.min_age,
                ct.max_age
            from course_groups cg
            join courses c on c.id = cg.course_id
            join course_types ct on ct.id = cg.course_type_id
            where c.gender = :gender
              and c.course_name = :course_name
              and ct.name = :group_type
        """),
        {
            "gender": gender,
            "course_name": course_name,
            "group_type": group_type
        }
    ).mappings().first()



# חדש
def delete_registration(db, registration_id):
    result = db.session.execute(
        db.text("""
            delete from registrations
            where id = :registration_id
            returning id
        """),
        {"registration_id": registration_id}
    )

    deleted = result.fetchone()

    if deleted:
        db.session.commit()
        return True

    return False


# חדש
def add_registrant_db(
    db,
    gender,
    course_name,
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
):
    # שליפת הקבוצה + גיל + קיבולת
    row = db.session.execute(
        db.text("""
            select
                cg.id as course_group_id,
                cg.capacity,
                ct.min_age,
                ct.max_age
            from course_groups cg
            join courses c on c.id = cg.course_id
            join course_types ct on ct.id = cg.course_type_id
            where c.gender = :gender
              and c.course_name = :course_name
              and ct.name = :group_type
        """),
        {
            "gender": gender,
            "course_name": course_name,
            "group_type": group_type
        }
    ).mappings().first()

    if not row:
        return "not_found", None

    # בדיקת גיל
    min_age = row["min_age"]
    max_age = row["max_age"]

    if not (min_age <= child_age <= max_age):
        return "age_error", (min_age, max_age)

    course_group_id = row["course_group_id"]
    capacity = row["capacity"]

    # ספירת רשומים פעילים
    current_count = db.session.execute(
        db.text("""
            select count(*)
            from registrations
            where course_group_id = :group_id
              and status = 'registered'
        """),
        {"group_id": course_group_id}
    ).scalar()

    status = "waiting" if current_count >= capacity else "registered"

    # הכנסת הרשומה
    db.session.execute(
        db.text("""
            insert into registrations (
                course_group_id,
                parent_first_name,
                parent_last_name,
                email,
                phone,
                child_first_name,
                child_age,
                child_gender,
                id_number,
                insurance,
                commitments,
                status
            )
            values (
                :course_group_id,
                :parent_first_name,
                :parent_last_name,
                :email,
                :phone,
                :child_first_name,
                :child_age,
                :child_gender,
                :id_number,
                :insurance,
                :commitments,
                :status
            )
        """),
        {
            "course_group_id": course_group_id,
            "parent_first_name": parent_name,
            "parent_last_name": parent_surname,
            "email": email,
            "phone": phone,
            "child_first_name": child_name,
            "child_age": child_age,
            "child_gender": gender,
            "id_number": id_number,
            "insurance": insurance,
            "commitments": commitments,
            "status": status
        }
    )

    db.session.commit()

    return status, None


# חדש
def toggle_commitment_db(db, registration_id):
    result = db.session.execute(
        db.text("""
            update registrations
            set commitments = not commitments
            where id = :registration_id
            returning id
        """),
        {"registration_id": registration_id}
    )

    db.session.commit()

    return result.rowcount > 0

# חדש
def get_registrations_for_course(db, gender, course_name, group_type):
    rows = db.session.execute(
        db.text("""
            select
                r.id,
                r.parent_first_name as parent_name,
                r.parent_last_name as parent_surname,
                r.child_first_name as child_name,
                r.child_age,
                r.child_gender,
                r.email,
                r.phone,
                r.insurance,
                r.commitments,
                r.status,
                c.course_name as course,
                ct.name as group_type
            from registrations r
            join course_groups cg on cg.id = r.course_group_id
            join courses c on c.id = cg.course_id
            join course_types ct on ct.id = cg.course_type_id
            where c.gender = :gender
              and c.course_name = :course_name
              and ct.name = :group_type
            order by r.id
        """),
        {
            "gender": gender,
            "course_name": course_name,
            "group_type": group_type
        }
    ).mappings().all()

    registered_list = [r for r in rows if r["status"] == "registered"]
    waiting_list = [r for r in rows if r["status"] == "waiting"]

    return registered_list, waiting_list

# חדש
def create_course_with_groups(
    db,
    course_name,
    gender_key,
    small_capacity,
    regular_capacity
):
    # יצירת קורס
    result = db.session.execute(
        db.text("""
            insert into courses (course_name, gender)
            values (:course_name, :gender)
            returning id
        """),
        {
            "course_name": course_name,
            "gender": gender_key
        }
    )

    course_id = result.scalar()

    # שליפת סוגי קורס
    type_rows = db.session.execute(
        db.text("select id, name from course_types")
    ).mappings().all()

    type_map = {row["name"]: row["id"] for row in type_rows}

    # small
    db.session.execute(
        db.text("""
            insert into course_groups (course_id, course_type_id, capacity)
            values (:course_id, :type_id, :capacity)
        """),
        {
            "course_id": course_id,
            "type_id": type_map["small"],
            "capacity": small_capacity
        }
    )

    # regular
    db.session.execute(
        db.text("""
            insert into course_groups (course_id, course_type_id, capacity)
            values (:course_id, :type_id, :capacity)
        """),
        {
            "course_id": course_id,
            "type_id": type_map["regular"],
            "capacity": regular_capacity
        }
    )

    db.session.commit()
    return True

# חדש
def update_course_prices(db, small_price, regular_price, months):
    # עדכון מחיר small
    db.session.execute(
        db.text("""
            update course_types
            set price = :price,
                duration_months = :months
            where name = 'small'
        """),
        {
            "price": small_price,
            "months": months
        }
    )

    # עדכון מחיר regular
    db.session.execute(
        db.text("""
            update course_types
            set price = :price,
                duration_months = :months
            where name = 'regular'
        """),
        {
            "price": regular_price,
            "months": months
        }
    )

    db.session.commit()
    return True

# חדש
def update_course_capacity(db, gender, course_name, group_type, new_capacity):
    result = db.session.execute(
        db.text("""
            update course_groups
            set capacity = :capacity
            where id = (
                select cg.id
                from course_groups cg
                join courses c on c.id = cg.course_id
                join course_types ct on ct.id = cg.course_type_id
                where c.course_name = :course_name
                  and c.gender = :gender
                  and ct.name = :group_type
            )
        """),
        {
            "capacity": new_capacity,
            "course_name": course_name,
            "gender": gender,
            "group_type": group_type
        }
    )

    if result.rowcount == 0:
        return False

    db.session.commit()
    return True

# חדש
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
# חדש
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
            order by c.gender, c.course_name, ct.name
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

