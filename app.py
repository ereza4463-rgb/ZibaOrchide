
import os
import uuid
import sqlite3
from datetime import datetime

from flask import (
    Flask, render_template, redirect,
    url_for, session, request
)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "local-development-only-key"
)

# محصولات فروشگاه
products = [
    {"id": 1, "name": "رژ لب", "price": 350000, "emoji": "💄"},
    {"id": 2, "name": "کرم مراقبتی", "price": 280000, "emoji": "🧴"},
    {"id": 3, "name": "عطر و ادکلن", "price": 750000, "emoji": "🌷"},
    {"id": 4, "name": "محصولات مراقبت پوست", "price": 420000, "emoji": "🧼"}
]

orders = {}


# دیتابیس پشتیبانی
def init_support_db():
    conn = sqlite3.connect("ziba_orchid.db")
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

    conn.commit()
    conn.close()


init_support_db()


# محاسبه اطلاعات سبد خرید
def get_cart_data():
    saved_cart = session.get("cart", {})
    cart_items = []
    total = 0

    for product in products:
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
        products=products,
        cart_count=cart_count
    )


# افزودن محصول به سبد خرید
@app.route("/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if any(p["id"] == product_id for p in products):
        cart = session.get("cart", {})
        key = str(product_id)

        cart[key] = cart.get(key, 0) + 1

        session["cart"] = cart
        session.modified = True

    return redirect(url_for("home"))
    cart = session.get("cart", {})
    cart_count = sum(cart.values())

    print("CART TEST:", cart)

    return render_template(
        "index.html",
        products=products,
        cart_count=cart_count
    )



# صفحه سبد خرید
@app.route("/cart")
def cart():
    return render_template("cart.html")


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


# صفحه پرداخت
@app.route("/checkout")
def checkout():
    cart_items, total = get_cart_data()

    if not cart_items:
        return redirect(url_for("cart"))

    return render_template(
        "payment.html",
        cart=cart_items,
        total=total
    )


# پرداخت آزمایشی موفق
@app.route("/payment/test-success")
def payment_success():
    cart_items, total = get_cart_data()

    if not cart_items:
        return redirect(url_for("cart"))

    order_id = str(uuid.uuid4())[:8]

    orders[order_id] = {
        "items": cart_items,
        "total": total,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    session["cart"] = {}

    return render_template(
        "payment_success.html",
        order_id=order_id,
        total=total
    )


# پرداخت آزمایشی ناموفق
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
            conn = sqlite3.connect("ziba_orchid.db")
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


if __name__ == "__main__":
    app.run(debug=True)
