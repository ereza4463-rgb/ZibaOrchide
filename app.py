

import os
import uuid
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, session, request

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "local-development-only-key"
)

orders = {}

products = [
    {"id": 1, "name": "رژ لب", "price": 350000, "emoji": "💄"},
    {"id": 2, "name": "کرم مراقبتی", "price": 280000, "emoji": "🧴"},
    {"id": 3, "name": "عطر و ادکلن", "price": 750000, "emoji": "🌷"},
    {"id": 4, "name": "محصولات مراقبت پوست", "price": 420000, "emoji": "🧼"}
]

@app.route("/")
def home():
    cart = session.get("cart", {})
    cart_count = sum(cart.values())
    return render_template(
        "index.html",
        products=products,
        cart_count=cart_count
    )

@app.route("/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if any(p["id"] == product_id for p in products):
        cart = session.get("cart", {})
        key = str(product_id)
        cart[key] = cart.get(key, 0) + 1
        session["cart"] = cart

    return redirect(url_for("home"))

@app.route("/cart")
def cart():
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

    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total
    )

@app.route("/update-cart/<int:product_id>/<action>", methods=["POST"])
def update_cart(product_id, action):
    cart = session.get("cart", {})
    key = str(product_id)

    if key in cart:
        if action == "increase":
            cart[key] += 1

        elif action == "decrease":
            cart[key] -= 1

            if cart[key] <= 0:
                cart.pop(key)

    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/clear-cart", methods=["POST"])
def clear_cart():
    session["cart"] = {}
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
def checkout():
    cart = session.get("cart", {})
    total = 0

    for product in products:
        quantity = cart.get(str(product["id"]), 0)
        total += quantity * product["price"]

    if total <= 0:
        return redirect(url_for("cart"))

    order_id = str(uuid.uuid4())[:8].upper()

    orders[order_id] = {
        "id": order_id,
        "amount": total,
        "status": "در انتظار پرداخت",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "items": cart.copy()
    }

    session["current_order"] = order_id

    return render_template(
        "payment.html",
        order=orders[order_id]
    )


@app.route("/payment/test-success", methods=["POST"])
def test_payment_success():
    order_id = session.get("current_order")
    order = orders.get(order_id)

    if not order or order["status"] != "در انتظار پرداخت":
        return redirect(url_for("cart"))

    order["status"] = "پرداخت آزمایشی موفق"

    session["cart"] = {}
    session.pop("current_order", None)

    return render_template(
        "payment_success.html",
        order=order
    )


@app.route("/payment/test-failed", methods=["POST"])
def test_payment_failed():
    order_id = session.get("current_order")
    order = orders.get(order_id)

    if not order or order["status"] != "در انتظار پرداخت":
        return redirect(url_for("cart"))

    order["status"] = "پرداخت آزمایشی ناموفق"

    return render_template(
        "payment_failed.html",
        order=order
    )

if __name__ == "__main__":
    app.run(debug=True)

