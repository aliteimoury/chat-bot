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


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
app = Flask(__name__)
app.secret_key = "ali_shap_secret_key_1404"  # کلید مخفی برای سشن

# ==================== تنظیمات ====================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "dolphin3"
PRODUCTS_FILE = "products.json"
LOGS_FILE = "chat_logs.json"
USERS_FILE = "users.json"

# کاربر ادمین (با ایمیل و رمز مشخص)
ADMIN_EMAIL = "aliteimouri8503@gmail.com"
ADMIN_PASSWORD = "33313850"


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


def chat_with_ai(user_message):
    products = load_products()

    mobiles = [p for p in products if p['category'] == 'موبایل']
    laptops = [p for p in products if p['category'] == 'لپ‌تاپ']
    headphones = [p for p in products if p['category'] == 'هدفون']
    tablets = [p for p in products if p['category'] == 'تبلت']
    watches = [p for p in products if p['category'] == 'ساعت هوشمند']

    user_lower = user_message.lower()
    category_filter = None

    if any(word in user_lower for word in ['گوشی', 'موبایل', 'سامسونگ', 'شیائومی', 'galaxy', 'redmi']):
        category_filter = 'موبایل'
        relevant_products = mobiles
    elif any(word in user_lower for word in ['لپتاپ', 'لپ تاپ', 'ایسوس', 'asus', 'tuf', 'notebook']):
        category_filter = 'لپ‌تاپ'
        relevant_products = laptops
    elif any(word in user_lower for word in ['هدفون', 'هندزفری', 'سونی', 'sony', 'ایرپاد']):
        category_filter = 'هدفون'
        relevant_products = headphones
    elif any(word in user_lower for word in ['تبلت', 'ipad', 'سرفیس']):
        category_filter = 'تبلت'
        relevant_products = tablets
    elif any(word in user_lower for word in ['ساعت', 'هوشمند', 'watch']):
        category_filter = 'ساعت هوشمند'
        relevant_products = watches
    else:
        relevant_products = products

    if relevant_products:
        products_text = ""
        for p in relevant_products:
            products_text += f"""
نام: {p['name']}
دسته: {p['category']}
قیمت: {p['price']}
مشخصات: {p['specs']}
توضیحات: {p['description']}
-----------------"""
    else:
        all_products_text = ""
        for p in products:
            all_products_text += f"- {p['name']} ({p['category']})\n"
        products_text = f"محصولات موجود:\n{all_products_text}"

    prompt = f"""تو یک دستیار فروشگاه حرفه‌ای به نام 'علی شاپ' هستی.

【 قوانین بسیار مهم 】
1. فقط و فقط بر اساس لیست محصولات زیر جواب بده.
2. اگر محصولی در لیست نیست، بگو "این محصول در فروشگاه ما موجود نیست".
3. تحت هیچ شرایطی از دانش خودت برای معرفی محصول جدید استفاده نکن.
4. دسته‌بندی محصولات را با هم قاطی نکن.

【 لیست دقیق محصولات فروشگاه 】
{products_text}

【 سوال کاربر 】
{user_message}

【 جواب (فقط بر اساس لیست بالا) 】"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 600
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        result = response.json()
        answer = result.get("response", "متأسفم، نتونستم جواب بدم.")
        if len(answer) > 550:
            answer = answer[:550] + "..."
        return answer.strip()
    except Exception as e:
        print("OLLAMA ERROR:", e)
        return f"خطا در ارتباط با مدل"







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
                                  login_password=password,
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
                                      register_password=password,
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
                                      register_password=password,
                                      login_error=None,
                                      register_success=None,
                                      show_register=True)

    users = load_users()
    if email in users:
        return render_template("login.html",
                                      register_error="این ایمیل قبلاً ثبت نام کرده است",
                                      register_email=email,
                                      register_password=password,
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
    answer = chat_with_ai(user_message)
    save_log(user_message, answer)
    return jsonify({"reply": answer})

@app.route('/admin')
def admin_panel():
    products = load_products()
    logs = load_logs()
    return render_template("admin.html", products=products, logs=logs, message=None)

@app.route('/add', methods=['POST'])
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
def edit_product():
    products = load_products()
    product_id = int(request.form['id'])
    product_name = request.form['name']

    for i, p in enumerate(products):
        if p["id"] == product_id:
            products[i] = {
                "id": product_id,
                "name": request.form['name'],
                "category": request.form['category'],
                "price": request.form['price'] + ' تومان',
                "specs": request.form['specs'],
                "description": request.form.get('description', '')
            }
            break

    save_products(products)
    flash(f'✅ محصول "{product_name}" با موفقیت ویرایش شد.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/run_scraper', methods=['POST'])
def run_scraper():
    data = request.get_json()

    category = data.get("category")
    count = int(data.get("count", 25))

    if category in ["mobile", "laptop"]:
        try:
            # اجرای اسکرپر همراه با فرستادن نوع دسته‌بندی
            digikala_scraper.scrape_digikala_phones(target_new_products=count, category_type=category)
            return jsonify({
                "success": True,
                "message": f"✅ {count} محصول جدید از دیجی‌کالا اضافه شد.",
                "count": count
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"❌ خطا در اجرای اسکرپر: {str(e)}"
            })

    return jsonify({
        "success": False,
        "message": "❌ این دسته‌بندی هنوز فعال نشده است."
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)