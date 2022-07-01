import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required, usd
import json
import requests

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///tracker.db")

db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL)")
db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id NUMERIC NOT NULL, coin TEXT NOT NULL, \
            amount NUMERIC NOT NULL, total_amount NUMERIC NOT NULL, price NUMERIC NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")

@app.route('/login', methods=["GET", "POST"])
def login():

    if request.method =="GET":
        return render_template("login.html")

    else:
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("login.html", invalidPassword=True)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

@app.route("/logout")
def logout():

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")

    else:
        # Get username, password and confirmation of password
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Server side validations for input

        # Checks for valid input
        if len(db.execute('SELECT username FROM users WHERE username = ?', username)) != 0:
            return render_template("register.html", usernameExists=True)
        elif password != confirmation:
            return render_template("register.html", invalidPassword=True)

        # Add new user to users db (includes: username and HASH of password)
        db.execute('INSERT INTO users (username, hash) VALUES(?, ?)', username, generate_password_hash(password))

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Log user in, i.e. Remember that this user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")


@app.route('/', methods=["GET", "POST"])
@login_required
def index():

    # Add a position
    if request.method == "POST":
        position = request.form.get("position")
        token = request.form.get("token").upper()
        amount = float(request.form.get("amount"))
        price = float(request.form.get("price"))

        available = db.execute("SELECT coin, amount FROM orders WHERE user_id = ? AND coin = ?", session["user_id"], token)

        # Buy position - no validation
        if position == "Buy":
            if available:
                db.execute("UPDATE orders SET amount = amount + ?, total_amount = total_amount + ?, price = price + ? WHERE user_id = ? AND coin = ?", amount, amount, amount * price, session["user_id"], token)
            else:
                db.execute("INSERT INTO orders (user_id, coin, amount, total_amount, price) VALUES (?, ?, ?, ?, ?)", session["user_id"], token, amount, amount, amount * price)
            list = get_portfolio()
            return render_template("index.html", list=list, successful=True)
        # Sell position - validation for enough in portfolio to sell
        else:
            if available[0]["amount"] < amount:
                list = get_portfolio()
                return render_template("index.html", list=list, notEnough=True)
            else:
                db.execute("UPDATE orders SET amount = amount - ? WHERE user_id = ? AND coin = ?", amount, session["user_id"], token)
                list = get_portfolio()
                return render_template("index.html", list=list, successful=True)
    # GET
    else:
        # Weighted average of buy price
        list = get_portfolio()
        return render_template("index.html", list=list)

# Function to query Binance API and get the price for the parameter token
def get_price(coin):

    key = f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT"
    data = requests.get(key)
    data = data.json()

    return data["price"]

# Function to query the database, get portofolio and for each token call get_price to have it's current price
def get_portfolio():

    list = db.execute("SELECT coin, amount, total_amount, price FROM orders WHERE user_id = ?", session["user_id"])

    for row in list:
        row["price"] = float(row["price"]) / float(row["total_amount"])
        row["current_price"] = float(get_price(row["coin"]))
        row["current_value"] = float(row["current_price"] * row["amount"])
        row["change"] = '{0:.2f}'.format((row["current_value"] - (row["price"] * row["amount"])) / (row["price"] * row["amount"])  * 100)

    return list
