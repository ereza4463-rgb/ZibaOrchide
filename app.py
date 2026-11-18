
import os
import json
import uuid
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, redirect,
    url_for, session, request
)

from werkzeug.utils import secure_filename


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "local-development-only-key"
)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

DB_NAME = "ziba_orchid.db"

# تنظیمات آپلود عکس
UPLOAD_FOLDER = os.path.join("static", "uploads")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


# اتصال به دیتابیس
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ساخت جدول‌ها
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            reply TEXT DEFAULT '',
            status TEXT DEFAULT 'در انتظار پاسخ',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE NOT NULL,
            platform TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            phone TEXT NOT NULL,
            items TEXT NOT NULL,
            total INTEGER NOT NULL,
            status TEXT DEFAULT 'سفارش جدید',
            created_at TEXT NOT NULL
        )
    """)

    # جدول محصولات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT DEFAULT '',
            image TEXT DEFAULT '',
            emoji TEXT DEFAULT '📦'
        )
    """)

    # ثبت محصولات اولیه فقط در صورت خالی بودن جدول
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]

    if count == 0:
        default_products = [
            ("رژ لب", 350000, "محصول فروشگاه زیبا ارکیده", "", "💄"),
            ("کرم مراقبتی", 280000, "محصول فروشگاه زیبا ارکیده", "", "🧴"),
            ("عطر و ادکلن", 750000, "محصول فروشگاه زیبا ارکیده", "", "🌷"),
            ("محصولات مراقبت پوست", 420000, "محصول فروشگاه زیبا ارکیده", "", "🧼")
        ]

        cursor.executemany("""
            INSERT INTO products
            (name, price, description, image, emoji)
            VALUES (?, ?, ?, ?, ?)
        """, default_products)

    conn.commit()
    conn.close()


init_db()


# دریافت محصولات از دیتابیس
def get_products():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM products
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# محاسبه اطلاعات سبد خرید
def get_cart_data():
    saved_cart = session.get("cart", {})
    cart_items = []
    total = 0

    for product in get_products():
        quantity = saved_cart.get(str(product["id"]), 0)

        if quantity > 0:
            item = product.copy()
            item["quantity"] = quantity
            item["subtotal"] = quantity * product["price"]

            cart_items.append(item)
            total += item["subtotal"]

    return cart_items, total


# صفحه اصلی
@app.route("/")
def home():
    cart = session.get("cart", {})
    cart_count = sum(cart.values())

    return render_template(
        "index.html",
        products=get_products(),
        cart_count=cart_count
    )


# افزودن محصول به سبد خرید
@app.route("/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM products WHERE id = ?",
        (product_id,)
    )

    product_exists = cursor.fetchone()
    conn.close()

    if product_exists:
        cart = session.get("cart", {})
        key = str(product_id)

        cart[key] = cart.get(key, 0) + 1

        session["cart"] = cart
        session.modified = True

    return redirect(url_for("home"))


# صفحه سبد خرید
@app.route("/cart")
def cart():
    cart_items, total = get_cart_data()

    return render_template(
        "cart.html",
        cart=cart_items,
        total=total
    )


# افزایش و کاهش تعداد
@app.route("/update-cart/<int:product_id>/<action>")
def update_cart(product_id, action):
    cart = session.get("cart", {})
    key = str(product_id)

    if key in cart:
        if action == "increase":
            cart[key] += 1

        elif action == "decrease":
            cart[key] -= 1

            if cart[key] <= 0:
                del cart[key]

    session["cart"] = cart
    return redirect(url_for("cart"))


# حذف محصول
@app.route("/remove/<int:product_id>")
def remove_product(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart

    return redirect(url_for("cart"))


# خالی کردن سبد
@app.route("/clear-cart")
def clear_cart():
    session["cart"] = {}
    return redirect(url_for("cart"))


# فرم ثبت سفارش
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart_items, total = get_cart_data()

    if not cart_items:
        return redirect(url_for("cart"))

    if request.method == "POST":
        platform = request.form.get("platform", "").strip()
        customer_id = request.form.get("customer_id", "").strip()
        phone = request.form.get("phone", "").strip()

        allowed_platforms = [
            "روبیکا", "بله", "واتساپ", "ایتا"
        ]

        if platform not in allowed_platforms:
            return "پیام‌رسان انتخاب‌شده معتبر نیست."

        if not customer_id or len(customer_id) > 100:
            return "آیدی واردشده معتبر نیست."

        clean_phone = phone.replace(" ", "").replace("-", "")

        if not clean_phone.isdigit() or not 10 <= len(clean_phone) <= 15:
            return "شماره تماس معتبر وارد کنید."

        order_code = str(uuid.uuid4())[:8].upper()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders
            (order_code, platform, customer_id, phone,
             items, total, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            order_code,
            platform,
            customer_id,
            clean_phone,
            json.dumps(cart_items, ensure_ascii=False),
            total,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        conn.commit()
        conn.close()

        session["cart"] = {}

        return render_template(
            "order_success.html",
            order_code=order_code
        )

    return render_template(
        "order_form.html",
        cart=cart_items,
        total=total
    )


# ورود مدیر
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if ADMIN_PASSWORD and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))

        return render_template(
            "admin_login.html",
            error="رمز عبور اشتباه است یا رمز مدیر تنظیم نشده است."
        )

    return render_template("admin_login.html", error="")


# بررسی دسترسی مدیر
def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


# پنل مدیریت
@app.route("/admin")
@admin_required
def admin_panel():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM orders
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    order_list = []

    for row in rows:
        order = dict(row)

        try:
            order["items"] = json.loads(order["items"])
        except (json.JSONDecodeError, TypeError):
            order["items"] = []

        order_list.append(order)

    return render_template(
        "admin.html",
        orders=order_list,
        products=get_products()
    )


# ثبت محصول جدید همراه با یک عکس
@app.route("/admin/products/add", methods=["POST"])
@admin_required
def add_product():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price_text = request.form.get("price", "").strip()

    image = request.files.get("image")

    if not name or len(name) > 100:
        return "نام محصول معتبر نیست."

    if not price_text.isdigit() or int(price_text) <= 0:
        return "قیمت محصول معتبر نیست."

    if not image or not image.filename:
        return "لطفاً عکس محصول را انتخاب کنید."

    original_name = secure_filename(image.filename)

    if "." not in original_name:
        return "فرمت عکس معتبر نیست."

    extension = original_name.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        return "فقط عکس‌های JPG، JPEG، PNG و WEBP مجاز هستند."

    # ساخت نام یکتا برای عکس
    filename = f"{uuid.uuid4().hex}.{extension}"

    image_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    image.save(image_path)

    # ذخیره محصول در دیتابیس
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (name, price, description, image, emoji)
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        int(price_text),
        description,
        filename,
        "📦"
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_panel"))


# بستن سفارش
@app.route("/admin/close-order/<int:order_id>", methods=["POST"])
@admin_required
def close_order(order_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, ("بسته‌شده", order_id))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_panel"))


# خروج مدیر
@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# پرداخت آزمایشی ناموفق قبلی
@app.route("/payment/test-failed")
def payment_failed():
    return render_template("payment_failed.html")


# صفحه پشتیبانی
@app.route("/support", methods=["GET", "POST"])
def support():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if name and subject and message:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO support_messages
                (name, subject, message)
                VALUES (?, ?, ?)
            """, (name, subject, message))

            conn.commit()
            conn.close()

            return """
                <h2 style="text-align:center; direction:rtl">
                    پیام شما با موفقیت ثبت شد.
                </h2>
                <p style="text-align:center">
                    <a href="/support">بازگشت به پشتیبانی</a>
                </p>
            """

    return render_template("support.html")


# مدیریت خطای حجم زیاد عکس
@app.errorhandler(413)
def too_large(error):
    return "حجم عکس نباید بیشتر از ۵ مگابایت باشد.", 413


if __name__ == "__main__":
    app.run(debug=True)
