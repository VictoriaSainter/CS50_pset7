from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
import time

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    if request.method =="GET":
        transactions = db.execute("SELECT company_share_code, SUM(num_shares_bought) as num_shares_bought FROM transactions  WHERE user_id = :userid GROUP BY company_share_code", userid=session["user_id"])
        users_shares_worth_in_cents = 0
        
        transactions = [d for d in transactions if d['num_shares_bought'] != 0]
        
        for transaction in transactions:
            stock_symbol = transaction["company_share_code"]
            stock_quote = lookup(stock_symbol)
            stock_price_in_dollar = stock_quote["price"]
            stock_price_in_cents = int(stock_quote["price"]*100)
            company_name = stock_quote["name"]
            num_shares_bought = int(transaction["num_shares_bought"])
            transaction["stock_price"] = '${:,.2f}'.format(stock_price_in_dollar)
            transaction["company_name"] = company_name
            stock_worth_in_cents = int(num_shares_bought * stock_price_in_cents)
            users_shares_worth_in_cents = users_shares_worth_in_cents + stock_worth_in_cents
            transaction["total_worth"] = '${:,.2f}'.format(stock_worth_in_cents/100)
            
        
        
        user_cash_list = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        cash_available = user_cash_list[0]["cash"]
        
        cash_available_in_cents = cash_available*100
        
        cash_available_in_dollars = '${:,.2f}'.format(cash_available)
        
        users_total_worth_in_dollars = (users_shares_worth_in_cents + cash_available_in_cents)/100
        users_total_worth_in_dollars = '${:,.2f}'.format(users_total_worth_in_dollars)
        
    
        
        return render_template("index.html", transactions=transactions, total=users_total_worth_in_dollars, cash=cash_available_in_dollars)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    
    #if loading the buy page
    if request.method =="GET":
        return render_template("buy.html")
    #if posting request to buy shares
    else:
        try:
            numShares = int(request.form["shares"])
        except ValueError:
            #Handle the exception
            return apology("Please use positive integer")
        if request.form["symbol"] == "":
            return apology("Stock symbol blank")
        elif request.form["shares"] =="":
            return apology("Missing shares")
        elif numShares <= 0:
            return apology("Invalid shares")

        #if the user puts a valid symbol and shares value in, then go to the database to find their user ID and decide if possible to buy shares
        else:
            #get stock symbol
            symbol = request.form["symbol"]
            #find out cost of stock
            result = lookup(symbol)
            #remember to use numShares, the number of shares the user wants to buy 
            cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])

            
            if result:
                costOfOneShare_dollars = result["price"]
                
                costOfOneShare_cents = costOfOneShare_dollars * 100
                shareSymbol = result["symbol"]
                cashAvailable_cents = cash[0]["cash"] * 100
                amountToBeDeducted_cents = numShares * costOfOneShare_cents
                
                transactionDateTime =   time.strftime('%Y-%m-%d %H:%M:%S')
                
                if cashAvailable_cents < amountToBeDeducted_cents:
                    return apology("insufficient funds")
                else:
                    amountRemaining_cents = cashAvailable_cents - amountToBeDeducted_cents
                    amountRemaining_dollars = amountRemaining_cents/100
                    amountToBeDeducted_dollars = amountToBeDeducted_cents/100
                    updateUser = db.execute("UPDATE users SET cash = :amountRemaining WHERE id = :userid", amountRemaining=amountRemaining_dollars, userid=session["user_id"])
                    updateTransactionTable = db.execute("INSERT INTO transactions (user_id, num_shares_bought, cost_of_share, company_share_code, total_paid, date_of_transaction) VALUES(:user_id, :num_shares_bought, :cost_of_share, :company_share_code, :total_paid, :date_of_transaction)", user_id=session["user_id"], num_shares_bought=numShares, cost_of_share=costOfOneShare_dollars, company_share_code=shareSymbol, total_paid=amountToBeDeducted_dollars, date_of_transaction=transactionDateTime)
                    
                    flash("Bought!")
                    return redirect(url_for("index"))
            else:
                return apology("Please enter a valid stock symbol")



@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    

    if request.method =="GET":
        transactions = db.execute("SELECT * FROM transactions  WHERE user_id = :userid", userid=session["user_id"])
        
        return render_template("history.html", transactions=transactions)
        
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")
        

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))
    
    
@app.route("/changepassword", methods=["GET", "POST"])
def changepassword():
    if request.method =="GET":
        
        return render_template("changepassword.html")
    else:
        if not request.form.get("current_password"):
            return apology("incorrect password, please try again")
        if not request.form.get("new_password"):
            return apology("please provide a new password")
        elif not request.form.get("new_password") == request.form.get("new_password_again"):
            return apology("please make sure your new passwords match")
            
        rows = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])
        if not pwd_context.verify(request.form.get("current_password"), rows[0]["hash"]):
            return apology("incorrect password")
        else:
            hashedPassword = pwd_context.encrypt(request.form["new_password"])
            updateUser = db.execute("UPDATE users SET hash = :hashedPassword WHERE id = :userid", hashedPassword=hashedPassword, userid=session["user_id"])
            
        flash("Password changed!")
        return redirect(url_for("index"))
        # forget any user_id
        
    

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method =="GET":
        return render_template("quote.html")
    else: 
        if request.form["symbol"] == "":
            return apology("Stock symbol blank")
        else: 
            symbol = request.form["symbol"]
            result = lookup(symbol)

            if result:
                
                return render_template("quoted.html", name=result['name'], price=result['price'], symbol=result['symbol'])
            else:
                return apology("Please enter a valid stock symbol")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    if request.method == "GET":
        return render_template("register.html")

    if request.method =="POST":
        # forget any user_id
        session.clear()
            
        if request.form["username"] == "":
            return apology("Username blank")
        
        if request.form["password"] =="" or request.form["passwordCheck"] =="": 
            return apology("Please fill both password fields")
        
        if request.form["password"] != request.form["passwordCheck"]:
            return apology("Your password doesn't match!")
            
        hashedPassword = pwd_context.encrypt(request.form["password"])
            
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form["username"], hash=hashedPassword)
        if not result:
            return apology("Username is already taken")
        
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")
        
        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        
        # redirect user to home page
        return redirect(url_for("index"))

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    #if loading the sell page
    if request.method =="GET":
        return render_template("sell.html")
    #if posting request to buy shares
    else:
        try:
            numShares = int(request.form["shares"])
        except ValueError:
            #Handle the exception
            return apology("Please use positive integer")
        if request.form["symbol"] == "":
            return apology("Stock symbol blank")
        elif request.form["shares"] =="":
            return apology("Missing shares")
        elif numShares <= 0:
            return apology("Invalid shares")
        
        #assuming symbol and number are relevant 
        #using the transactions table, check to see if the user has the share that they want to sell, first by symbol, then by quantity
        else:
            stock_symbol = request.form["symbol"].upper()
            transactions = db.execute("SELECT company_share_code, SUM(num_shares_bought) as num_shares_bought FROM transactions  WHERE user_id = :userid GROUP BY company_share_code", userid=session["user_id"])
            
            for transaction in transactions:
                #check if user has enough shares with right symbol to sell
                if transaction["num_shares_bought"] >= numShares and stock_symbol == transaction["company_share_code"]:
                    
                    #look up the stock price and check if valid symbol
                    stock_quote_output = lookup(stock_symbol)
                    if(stock_quote_output) :
                        value_of_one_stock_in_cents = stock_quote_output['price'] * 100
                        value_of_one_stock_in_dollars = stock_quote_output['price']
                        value_to_be_sold_in_cents =  value_of_one_stock_in_cents * numShares

                        cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
                        user_balance_in_cents = cash[0]["cash"]*100
                        new_user_balance_in_cents = value_to_be_sold_in_cents + user_balance_in_cents
                        new_user_balance_in_dollars = new_user_balance_in_cents/100
                        transactionDateTime =   time.strftime('%Y-%m-%d %H:%M:%S')
                        #update the users balance
                        updateUser = db.execute("UPDATE users SET cash = :new_user_balance_in_dollars WHERE id = :userid", new_user_balance_in_dollars=new_user_balance_in_dollars, userid=session["user_id"])
                        #update the transaction table
                        numShares = numShares*-1
                        value_to_be_sold_in_dollars = value_to_be_sold_in_cents/-100
                        updateTransactionTable = db.execute("INSERT INTO transactions (user_id, num_shares_bought, cost_of_share, company_share_code, total_paid, date_of_transaction) VALUES(:user_id, :num_shares_bought, :cost_of_share, :company_share_code, :total_paid, :date_of_transaction)", user_id=session["user_id"], num_shares_bought=numShares, cost_of_share=value_of_one_stock_in_dollars, company_share_code=stock_symbol, total_paid=value_to_be_sold_in_dollars, date_of_transaction=transactionDateTime)
                        
                        flash("Sold!")
                        return redirect(url_for("index"))
                    else:
                        return apology("Please enter valid stock symbol")
            return apology("Shares not available to sell")


