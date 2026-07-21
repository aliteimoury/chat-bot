from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
from flask import flash
import json
import time
import os
from datetime import datetime
import re
import hashlib
import digikala_scraper
from datetime import timedelta
from functools import wraps


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
app = Flask(__name__)
app.secret_key = "ali_shap_secret_key_1404"

# ✅ این تنظیمات رو اضافه کن
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_USE_SIGNER'] = True

# ==================== تنظیمات ====================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "dolphin3"
PRODUCTS_FILE = "products.json"
LOGS_FILE = "chat_logs.json"
USERS_FILE = "users.json"

# کاربر ادمین (با ایمیل و رمز مشخص)
ADMIN_EMAIL = "aliteimouri8503@gmail.com"
ADMIN_PASSWORD = "33313850"
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_email') != ADMIN_EMAIL:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_logs():
    if not os.path.exists(LOGS_FILE):
        return []
    with open(LOGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def save_log(question, answer):
    try:
        with open(LOGS_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except:
        logs = []

    logs.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question": question,
        "answer": answer
    })

    with open(LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def normalize_text(text):
    """اعداد فارسی/عربی رو به انگلیسی تبدیل میکنه و حروف رو یکدست میکنه"""
    if not text:
        return ""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    trans = str.maketrans(persian_digits + arabic_digits, english_digits + english_digits)
    return text.translate(trans).lower().strip()

STOPWORDS = {
    "گوشی", "موبایل", "مدل", "محصول", "قیمت", "مشخصات", "گیگابایت",
    "گیگ", "رم", "حافظه", "تومان", "چنده", "چقدر", "هست", "آیا",
    "لطفا", "لطفاً", "میخوام", "برام", "درباره", "معرفی", "کن"
}

def find_matching_products(user_message, products):
    """جستجوی هوشمند روی تمام محصولات - مستقل از تعداد و ترتیب"""
    user_norm = normalize_text(user_message)
    user_words = set(
        w for w in re.findall(r'[\w\u0600-\u06FF]+', user_norm)
        if len(w) > 2 and w not in STOPWORDS
    )
    scored = []
    for p in products:
        name_norm = normalize_text(p['name'])
        if name_norm in user_norm:
            scored.append((p, 1000))
            continue
        name_words = set(
            w for w in re.findall(r'[\w\u0600-\u06FF]+', name_norm)
            if len(w) > 2 and w not in STOPWORDS
        )
        overlap = user_words & name_words
        if overlap:
            scored.append((p, len(overlap)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored][:20]


def chat_with_ai(user_message, conversation_history=None):
    products = load_products()
    
    if conversation_history is None:
        conversation_history = []
    
    # ===== بررسی دقیق تر محصولات =====
    # لیست کامل نام محصولات برای تشخیص
    product_names = []
    for p in products:
        product_names.append(p['name'].lower())
        # اضافه کردن کلمات کلیدی هر محصول
        words = p['name'].split()
        for word in words:
            if len(word) > 3:  # کلمات با طول بیشتر از ۳
                product_names.append(word.lower())
    
    mentioned_products = find_matching_products(user_message, products)

    # اگه توی پیام فعلی محصولی پیدا نشد، شاید سوال ادامه‌داره
    # (مثل «قیمتشون چنده؟» یا «کدومش بهتره؟») - چندتا پیام آخر مکالمه رو هم بگرد
    if not mentioned_products and conversation_history:
        recent_text = " ".join(msg['content'] for msg in conversation_history[-6:])
        mentioned_products = find_matching_products(recent_text, products)

    product_found = len(mentioned_products) > 0

    if not product_found:
        # اگه کاربر اصلاً کلمه‌ی مرتبط با محصول نگفته (مثلاً فقط سلام کرده)
        # به‌جای «موجود نیست»، چندتا نمونه محصول معرفی کن
        user_norm = normalize_text(user_message)
        has_product_keyword = any(
            len(w) > 2 and w not in STOPWORDS
            for w in re.findall(r'[\w\u0600-\u06FF]+', user_norm)
        )
        if not has_product_keyword:
            sample_text = "\n".join(f"- {p['name']}" for p in products[:5])
            return f"سلام! 👋 می‌تونید درباره‌ی قیمت، مشخصات یا مقایسه‌ی محصولاتی مثل این‌ها بپرسید:\n{sample_text}"
        return "متأسفم، این محصول در حال حاضر در فروشگاه علی‌شاپ موجود نیست. لطفاً نام دقیق‌تری از محصول مورد نظرتون رو امتحان کنید 🙏"

    products_text = ""
    if mentioned_products:
        for p in mentioned_products[:15]:
            products_text += f"""
نام: {p['name']}
دسته: {p['category']}
قیمت: {p['price']}
مشخصات: {p['specs']}
-----------------"""
    else:
        all_products = ""
        for p in products[:5]:
            all_products += f"- {p['name']} ({p['category']})\n"
        products_text = f"محصولات موجود:\n{all_products}"

    history_text = ""
    if conversation_history:
        history_text = "\n【 تاریخچه مکالمه 】\n"
        for msg in conversation_history[-10:]:
            role_label = "کاربر" if msg['role'] == 'user' else "دستیار"
            history_text += f"{role_label}: {msg['content']}\n"
        history_text += "\n"

    main_instruction = """
【 قوانین طلایی - بسیار مهم 】
1. فقط از داده‌ی محصولاتی که در لیست پایین بهت داده میشه استفاده کن؛ این تنها منبع اطلاعاتی توئه.
2. تحت هیچ شرایطی از دانش عمومی خودت درباره‌ی گوشی‌ها، قیمت‌ها یا مشخصات استفاده نکن، حتی اگه مطمئن باشی درسته.
3. اگر کاربر درباره‌ی محصولی پرسید که در لیست نیست، دقیقاً بگو: "متأسفم، این محصول در حال حاضر در فروشگاه علی شاپ موجود نیست."
4. هیچ‌وقت قیمت یا مشخصات محصولی که در لیست نیست رو حدس نزن.
5. برای سوال قیمت فقط از فیلد «قیمت»، برای مشخصات فقط از فیلد «مشخصات» استفاده کن؛ خلاصه و مرتب بنویس.
6. برای مقایسه‌ی چند محصول، فقط اونایی که در لیست هستن رو مقایسه کن.
7. لحن مودب و حرفه‌ای مثل یک فروشنده‌ی مطلع داشته باش.
"""

    prompt = f"""تو یک دستیار فروشگاه به نام 'علی شاپ' هستی.

{main_instruction}

【 لیست محصولات فروشگاه 】
{products_text}

{history_text}

【 سوال کاربر 】
{user_message}

【 پاسخ (فقط بر اساس لیست بالا) 】"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 400
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        result = response.json()
        answer = result.get("response", "متأسفم، نتونستم جواب بدم.")
        
        # ===== شبکه‌ی ایمنی سبک: اگه محصول خاصی خواسته شده ولی اسمش در پاسخ نیومده، یادآوری کن =====
        answer_norm = normalize_text(answer)
        if product_found:
            product_in_answer = any(normalize_text(p['name']) in answer_norm for p in mentioned_products)
            if not product_in_answer and "موجود نیست" not in answer:
                names = "، ".join(p['name'] for p in mentioned_products[:3])
                answer += f"\n\n(ℹ️ بر اساس اطلاعات محصول: {names})"

        return answer.strip()
        
    except requests.exceptions.Timeout:
        print("OLLAMA TIMEOUT")
        return "⏰ زمان پاسخگویی به پایان رسید. لطفاً دوباره تلاش کنید."
    except Exception as e:
        print("OLLAMA ERROR:", e)
        return "❌ خطا در ارتباط با مدل. لطفاً دوباره تلاش کنید."


def validate_product_answer(answer, products):
    """بررسی میکنه که پاسخ مدل فقط شامل محصولات موجود باشه"""
    
    # پیدا کردن تمام اسم‌های محصولات در پاسخ
    mentioned_in_answer = []
    for p in products:
        if p['name'].lower() in answer.lower():
            mentioned_in_answer.append(p['name'])
    
    # اگر محصولی در پاسخ هست که در لیست نیست
    # (این تابع فعلاً فقط برای لاگ‌گیری استفاده میشه)
    
    return mentioned_in_answer


# ==================== مسیرها ====================

@app.route('/')
def index():
    if 'user_email' in session:
        products = load_products()
        from datetime import datetime
        is_admin = (session.get('user_email') == ADMIN_EMAIL)
        return render_template("chat.html", products=products, now=datetime.now().strftime("%H:%M"),
                                      user_email=session['user_email'], is_admin=is_admin)
    return render_template("login.html", login_error=None, register_error=None, register_success=None)


@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    users = load_users()

    if email == ADMIN_EMAIL and hash_password(password) == hash_password(ADMIN_PASSWORD):
        session['user_email'] = email
        return redirect(url_for('index'))

    if email in users and users[email] == hash_password(password):
        session['user_email'] = email
        return redirect(url_for('index'))

    return render_template("login.html",
                                  login_error="ایمیل یا رمز عبور اشتباه است",
                                  login_email=email,
                                  register_error=None,
                                  register_success=None)


@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email')
    password = request.form.get('password')

    if not is_valid_email(email):
        return render_template("login.html",
                                      register_error="فقط ایمیل‌های Gmail معتبر هستند",
                                      register_email=email,
                                      login_error=None,
                                      register_success=None,
                                      show_register=True)
    if not email.endswith('@gmail.com'):
        return render_template("login.html", register_error="فقط ایمیل‌های Gmail معتبر هستند (example@gmail.com)",
                                      login_error=None, register_success=None, show_register=True)
    if len(password) < 8:
        return render_template("login.html",
                                      register_error="رمز عبور حداقل ۸ کاراکتر باشد",
                                      register_email=email,
                                      login_error=None,
                                      register_success=None,
                                      show_register=True)

    users = load_users()
    if email in users:
        return render_template("login.html",
                                      register_error="این ایمیل قبلاً ثبت نام کرده است",
                                      register_email=email,
                                      login_error=None,
                                      register_success=None,
                                      show_register=True)

    users[email] = hash_password(password)
    save_users(users)

    return render_template("login.html",
                                  register_success="✅ ثبت نام موفق! اکنون وارد شوید",
                                  register_error=None,
                                  login_error=None)


def save_products(products):
    # قبل از ذخیره، ID ها رو بازسازی کن
    for index, product in enumerate(products, start=1):
        product["id"] = index
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/chat', methods=['POST'])
def chat():
    if 'user_email' not in session:
        return jsonify({"reply": "لطفاً ابتدا وارد شوید"})

    data = request.get_json()
    user_message = data.get('message', '')
    
    # **تاریخچه مکالمه رو از سشن بگیر**
    if 'conversation_history' not in session:
        session['conversation_history'] = []
    
    conversation_history = session['conversation_history']
    
    # **سوال کاربر رو به تاریخچه اضافه کن**
    conversation_history.append({
        'role': 'user',
        'content': user_message
    })
    
    # **جواب رو بگیر (با تاریخچه)**
    answer = chat_with_ai(user_message, conversation_history)
    
    # **جواب رو به تاریخچه اضافه کن**
    conversation_history.append({
        'role': 'assistant',
        'content': answer
    })
    if len(conversation_history) > 80:
        conversation_history = conversation_history[-80:]
    
    # **تاریخچه رو در سشن ذخیره کن - این خط مهمه!**
    session['conversation_history'] = conversation_history
    session.modified = True  # ✅ این خط رو حتماً اضافه کن

    # **لاگ رو ذخیره کن**
    save_log(user_message, answer)

    return jsonify({"reply": answer})
    

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    if 'user_email' in session:
        # پاک کردن تاریخچه مکالمه
        session.pop('conversation_history', None)
        session.modified = True  # ✅ این خط رو حتماً اضافه کن
        return jsonify({"success": True, "message": "چت جدید شروع شد"})
    return jsonify({"success": False, "message": "لطفاً وارد شوید"})

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)  # ۳۰ دقیقه

@app.route('/admin')
@admin_required
def admin_panel():
    products = load_products()
    logs = load_logs()
    
    # محاسبه تعداد محصولات هر دسته
    categories = {}
    for p in products:
        cat = p.get('category', 'سایر')
        categories[cat] = categories.get(cat, 0) + 1
    
    return render_template("admin.html", products=products, logs=logs, categories=categories, message=None)

@app.route('/add', methods=['POST'])
@admin_required
def add_product():
    products = load_products()
    new_id = max([p["id"] for p in products]) + 1 if products else 1

    raw_price = request.form.get('price', '')
    if raw_price:
        price = raw_price + ' تومان'
    else:
        price = 'نامشخص'

    specs = request.form.get('specs', '')
    if not specs:
        specs = "مشخصات کامل نشده است"

    new_product = {
        "id": new_id,
        "name": request.form['name'],
        "category": request.form['category'],
        "price": price,
        "specs": specs,
        "description": request.form.get('description', '')
    }
    products.append(new_product)
    save_products(products)

    flash(f'✅ محصول "{request.form["name"]}" با موفقیت اضافه شد.', 'success')
    return redirect(url_for('admin_panel'))

def reindex_products():
    """بازسازی ID های محصولات به ترتیب از 1 شروع میشه"""
    products = load_products()
    for index, product in enumerate(products, start=1):
        product["id"] = index
    save_products(products)
    return products


@app.route('/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    products = load_products()

    # پیدا کردن اسم محصول
    product_name = next((p["name"] for p in products if p["id"] == product_id), None)

    # حذف محصول
    products = [p for p in products if p["id"] != product_id]
    save_products(products)

    # بازسازی ID ها
    reindex_products()

    flash(f'✅ محصول "{product_name}" با موفقیت حذف شد.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/edit', methods=['POST'])
@admin_required
def edit_product():
    products = load_products()
    product_id = int(request.form['id'])
    product_name = request.form['name']
    raw_price = request.form['price']

    # حذف همه کاراکترهای غیرعددی از قیمت
    clean_price = ''.join(filter(str.isdigit, raw_price))
    
    # اگر عدد بود، با کاما فرمت کن
    if clean_price:
        # تبدیل به عدد و فرمت با کاما
        price_num = int(clean_price)
        formatted_price = f"{price_num:,} تومان"
    else:
        formatted_price = "نامشخص"

    for i, p in enumerate(products):
        if p["id"] == product_id:
            products[i] = {
                "id": product_id,
                "name": request.form['name'],
                "category": request.form['category'],
                "price": formatted_price,
                "specs": request.form['specs'],
                "description": request.form.get('description', '')
            }
            break

    save_products(products)
    flash(f'🔁 محصول "{product_name}" با موفقیت ویرایش شد.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/run_scraper', methods=['POST'])
@admin_required
def run_scraper():
    data = request.get_json()

    category = data.get("category")
    count = int(data.get("count", 25))

    # تعیین پارامترهای پویا بر اساس دسته انتخابی کاربر
    if category == "mobile":
        category_slug = "mobile-phone"
        category_name = "موبایل"
    elif category == "tablet":
        category_slug = "tablet"
        category_name = "تبلت"
    elif category == "watch":
        category_slug = "wearable-gadget"
        category_name = "ساعت هوشمند"
    else:
        return jsonify({
            "success": False,
            "message": "❌ این دسته‌بندی هنوز فعال نشده است."
        })

    try:
        # اجرای اسکرپر با فرستادن اطلاعات دسته‌بندی جدید
        digikala_scraper.scrape_digikala_phones(
            target_new_products=count,
            category_slug=category_slug,
            category_name=category_name
        )
        return jsonify({
            "success": True,
            "message": f"✅ {count} {category_name} جدید از دیجی‌کالا اضافه شد.",
            "count": count
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"❌ خطا در اجرای اسکرپر: {str(e)}"
        })


if __name__ == '__main__':
    app.run(debug=True, port=5000)