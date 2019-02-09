import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Show stocks owned, shares of each stock, current price of each stock, total price for each
    # user's cash balance
    # grand total

    # Get stocks owned by user
    users = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    stocks = db.execute("SELECT symbol, name, SUM(shares) as total_shares, SUM(total) as total_owned \
                FROM transactions WHERE user_id = :user_id \
                GROUP BY symbol HAVING total_shares > 0",
                user_id=session["user_id"])
    quotes = {}
    capital = 0.0

    # Iterate through stocks to display correct information
    for stock in stocks:
        quotes[stock["symbol"]] = lookup(stock["symbol"])
        stock["total"] = stock["total_owned"]

        capital += stock["total"]

    # Get amount of cash remaining
    cash_remaining = users[0]["cash"]


    return render_template("index.html", quotes=quotes, stocks=stocks, cash_remaining=cash_remaining, grand_total=usd(cash_remaining + capital))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Check for correct method
    if request.method == "GET":
        return render_template ("buy.html")

    # Find stock value
    elif request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Symbol not found.")

    # Check if the number entered is a pòsitive integer
    try:
        shares = int(request.form.get("shares"))
    except:
        return apology("number has to be a positive integer")

    if not shares > 0:
        return apology("number has to be a positive integer")

    # Go to user id and check if they can make the purchase
    rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

    # Set variables for database
    cash_remaining = rows[0]["cash"]
    stock_value = quote["price"]
    name = quote["name"]
    purchase_value = stock_value * shares
    total = purchase_value
    action = "Purchase"

    # Check if user has enough money
    if purchase_value > cash_remaining:
        return apology("Sorry, not enough money")

    # Store info in database
    db.execute("UPDATE users SET cash = cash - :purchase_value WHERE id = :user_id", purchase_value=purchase_value, user_id=session["user_id"])
    db.execute("INSERT INTO transactions (user_id, symbol, name, shares, stock_value, total, action) VALUES (:user_id, :symbol, :name, :shares, :stock_value, :total, :action)",
                user_id = session["user_id"], symbol = request.form.get("symbol"), name = name, shares = shares, stock_value = stock_value, total = total, action=action)

    flash("Bought!")

    return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Retrieve info from database
    transactions = db.execute("SELECT symbol, name, shares, stock_value, since, action \
                FROM transactions WHERE user_id = :user_id", \
                user_id=session["user_id"])

    # If user hasn't made any transactions yet
    if not transactions:
        return apology("Nothing to display")

    # Set info to display, always show positive shares and totals.
    else:
        for transaction in transactions:
            transaction["stock_vaue"] = usd(transaction["stock_value"])
            transaction["shares"] = int(transaction["shares"])

            if (transaction["shares"] < 0):
                transaction["shares"] = -(transaction["shares"])

        return render_template("history.html", transactions = transactions)

@app.route("/money", methods=["GET", "POST"])
@login_required
def money():
    """ Adds money to user's account"""

    # Check for correct input from user
    if request.method == "POST":
        try:
            money = float(request.form.get("money"))
        except:
            return apology("Sorry, must enter a positive amount")

        # Set variables for database
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        current_cash = cash[0]["cash"]
        action = "Deposit"
        symbol = "Cash"
        name = "Deposit"
        stock_value = int(request.form.get("money"))
        shares = 1
        total = shares * stock_value

        # Store deposit info to database
        db.execute("UPDATE users SET cash = cash + :money WHERE id = :user_id", money=money, user_id=session["user_id"])
        db.execute("INSERT INTO transactions (user_id, total, action, symbol, name, stock_value, shares) VALUES (:user_id, :total, :action, :symbol, :name, :stock_value, :shares)",\
                    total=total, action=action, symbol=symbol, name=name, stock_value=stock_value, shares=shares, user_id=session["user_id"])

        flash("Cash added successfully")

        return redirect("/")

    # If methof not POST
    else:
        return render_template("/money.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # Check for correct input from user
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Symbol not found.")

        # Display information in quoted.html
        return render_template("quoted.html", quote = quote)

    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Ensure password_check was submitted
        elif not request.form.get("password_check"):
            return apology("must re-type password")

        elif request.form.get("password") != request.form.get("password_check"):
            return apology("passwords do not match")

        # Hash password for username given
        hash = generate_password_hash(request.form.get("password"))

        # Add user to database
        new_user = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                    username=request.form.get("username"), hash=hash)

        if not new_user:
            return apology("username already exists")

        # Log in new member
        session["user_id"] = new_user

        flash("registered successfully!")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Find stock value
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Symbol not found.")

        # Check if the number entered is a pòsitive integer
        try:
            shares_sold = int(request.form.get("shares"))
        except:
            return apology("number has to be a positive integer")

        if not shares_sold > 0:
            return apology("number has to be a positive integer")

        # Go to user id and check if they can make the sell
        # Check if user has stocks to sell

        shares_owned = db.execute("SELECT SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id AND symbol = :symbol GROUP BY symbol",
                           user_id=session["user_id"], symbol=request.form.get("symbol"))

        if len(shares_owned) != 1 or shares_owned[0]["total_shares"] <= 0 or shares_owned[0]["total_shares"] < shares_sold:
            return apology("Sorry, can't make that sell")

        cash_remaining = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # Update price and sell
        # Add earnings to current cash
        stock_value = quote["price"]
        sell_value = stock_value * shares_sold

        total = -(sell_value)
        name = quote["name"]
        shares = -(shares_sold)
        action = "Sell"

        # Update database
        db.execute("UPDATE users SET cash = cash + :sell_value WHERE id = :user_id", sell_value=sell_value, user_id=session["user_id"])
        db.execute("INSERT INTO 'transactions' (user_id, symbol, name, shares, stock_value, total, action) VALUES (:user_id, :symbol, :name, :shares, :stock_value, :total, :action)",
                user_id = session["user_id"], symbol = request.form.get("symbol"), name = name, shares = shares, stock_value = stock_value, total = total, action=action)

        flash("Sold!")

        return redirect("/")

    elif request.method == "GET":
        return render_template ("sell.html")

@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change user's password"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure current password was submitted
        if not request.form.get("old_password"):
            return apology("must provide current password")

        # Ensure new password was submitted
        elif not request.form.get("password"):
            return apology("must provide new password")

        # Ensure password_check was submitted
        elif not request.form.get("password_check"):
            return apology("must re-type new password")

        elif request.form.get("password") != request.form.get("password_check"):
            return apology("passwords do not match")

        # Check for correct password
        old_hash = db.execute("SELECT hash FROM users WHERE id = :user_id", user_id=session["user_id"])

        if not (check_password_hash(old_hash[0]["hash"], request.form.get("old_password"))):
                return apology("sorry, wrong password")

        # Hash password for username given
        new_hash = generate_password_hash(request.form.get("password"))

        # Update password to database
        db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", hash=new_hash, user_id=session["user_id"])

        flash("Password changed successfully!")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("password.html")


def errorhandler(e):
    """Handle error"""
    return apology("error", 403)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
