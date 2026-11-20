from datetime import datetime, date

from sqlalchemy import inspect, text

from flask import Flask, render_template, redirect, url_for, request, flash

from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)

from werkzeug.security import generate_password_hash, check_password_hash

# ==========================================
# 1. APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "pennywise-development-secret-change-later"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pennywise.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access your dashboard."


# ==========================================
# 2. DATABASE MODELS
# ==========================================


class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    transactions = db.relationship(
        "Transaction", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    budgets = db.relationship(
        "Budget", backref="user", lazy=True, cascade="all, delete-orphan"
    )


class Transaction(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)

    amount = db.Column(db.Float, nullable=False)

    transaction_type = db.Column(db.String(20), nullable=False)

    category = db.Column(db.String(80), nullable=False)

    description = db.Column(db.Text)

    transaction_date = db.Column(db.Date, nullable=False, default=date.today)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Budget(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    category = db.Column(db.String(80), nullable=False)

    amount = db.Column(db.Float, nullable=False)

    month = db.Column(db.Integer, nullable=False)

    year = db.Column(db.Integer, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class SavingGoal(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(100), nullable=False)

    target_amount = db.Column(db.Float, nullable=False)

    amount_saved = db.Column(db.Float, nullable=False, default=0)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# ==========================================
# 3. LOGIN MANAGER
# ==========================================


@login_manager.user_loader
def load_user(user_id):

    return db.session.get(User, int(user_id))


# ==========================================
# 4. HOMEPAGE
# ==========================================


@app.route("/")
def index():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


# ==========================================
# 5. USER REGISTRATION
# ==========================================


@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        confirm_password = request.form.get("confirm_password", "")

        # Validate required fields

        if not name or not email or not password or not confirm_password:

            flash("Please complete all required fields.", "danger")

            return redirect(url_for("register"))

        # Validate password length

        if len(password) < 8:

            flash("Password must contain at least 8 characters.", "danger")

            return redirect(url_for("register"))

        # Confirm password

        if password != confirm_password:

            flash("Passwords do not match.", "danger")

            return redirect(url_for("register"))

        # Check existing email

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:

            flash("This email is already registered.", "warning")

            return redirect(url_for("register"))

        # Hash password

        hashed_password = generate_password_hash(password)

        # Create user

        new_user = User(name=name, email=email, password=hashed_password)

        try:

            db.session.add(new_user)

            db.session.commit()

            flash("Account created successfully. Please log in.", "success")

            return redirect(url_for("login"))

        except Exception:

            db.session.rollback()

            flash("Registration failed. Please try again.", "danger")

            return redirect(url_for("register"))

    return render_template("register.html")


# ==========================================
# 6. USER LOGIN
# ==========================================


@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            login_user(user)

            flash("Welcome back to PennyWise!", "success")

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# ==========================================
# 7. USER LOGOUT
# ==========================================


@app.route("/logout")
@login_required
def logout():

    logout_user()

    flash("You have successfully logged out.", "success")

    return redirect(url_for("login"))


# ==========================================
# 8. DASHBOARD
# ==========================================


@app.route("/dashboard")
@login_required
def dashboard():

    transactions = Transaction.query.filter_by(user_id=current_user.id).all()

    # Calculate the total income

    total_income = sum(t.amount for t in transactions if t.transaction_type == "income")

    # Calculate total expenses

    total_expenses = sum(
        t.amount for t in transactions if t.transaction_type == "expense"
    )
    # Calculate available balana

    balance = total_income - total_expenses

    today = date.today()

    # Get this month transaction

    monthly_transactions = [
        t
        for t in transactions
        if t.transaction_date.month == today.month
        and t.transaction_date.year == today.year
    ]

    monthly_income = sum(
        t.amount for t in monthly_transactions if t.transaction_type == "income"
    )

    monthly_expenses = sum(
        t.amount for t in monthly_transactions if t.transaction_type == "expense"
    )

    # Prepare six months of cash flow data

    chart_labels = []
    chart_income = []
    chart_expenses = []

    for offset in range(5, -1, -1):

        month_index = today.year * 12 + today.month - 1 - offset

        year = month_index // 12
        month = month_index % 12 + 1

        chart_date = date(year, month, 1)

        chart_labels.append(chart_date.strftime("%b %Y"))

        month_transactions = [
            t
            for t in transactions
            if t.transaction_date.month == month and t.transaction_date.year == year
        ]

        income = sum(
            t.amount for t in month_transactions if t.transaction_type == "income"
        )

        expenses = sum(
            t.amount for t in month_transactions if t.transaction_type == "expense"
        )

        chart_income.append(income)
        chart_expenses.append(expenses)

    # Give the five most recent transaction

    recent_transactions = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(5)
        .all()
    )

    savings_goal = SavingGoal.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "dashboard.html",
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        recent_transactions=recent_transactions,
        savings_goal=savings_goal,
        chart_labels=chart_labels,
        chart_income=chart_income,
        chart_expenses=chart_expenses,
    )


# ==========================================
# 9. VIEW TRANSACTIONS
# ==========================================


@app.route("/transactions")
@login_required
def transactions():

    all_transactions = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .all()
    )

    return render_template("transactions.html", transactions=all_transactions)


# ==========================================
# 10. ADD TRANSACTION
# ==========================================


@app.route("/add-transaction", methods=["GET", "POST"])
@login_required
def add_transaction():

    if request.method == "POST":

        title = request.form.get("title", "").strip()

        amount = request.form.get("amount", "")

        transaction_type = request.form.get("transaction_type", "")

        category = request.form.get("category", "").strip()

        description = request.form.get("description", "").strip()

        transaction_date = request.form.get("transaction_date", "")

        if not title or not category or not amount:

            flash("Please complete all required fields.", "danger")

            return redirect(url_for("add_transaction"))

        try:

            amount = float(amount)

            if amount <= 0:
                raise ValueError

            if transaction_type not in ["income", "expense"]:
                raise ValueError

            selected_date = (
                datetime.strptime(transaction_date, "%Y-%m-%d").date()
                if transaction_date
                else date.today()
            )

        except ValueError:

            flash("Please enter valid transaction details.", "danger")

            return redirect(url_for("add_transaction"))

        transaction = Transaction(
            title=title,
            amount=amount,
            transaction_type=transaction_type,
            category=category,
            description=description,
            transaction_date=selected_date,
            user_id=current_user.id,
        )

        db.session.add(transaction)

        db.session.commit()

        flash("Transaction added successfully!", "success")

        return redirect(url_for("transactions"))

    return render_template("add_transaction.html")


# ==========================================
# 11. EDIT TRANSACTION
# ==========================================


@app.route("/edit-transaction/<int:transaction_id>", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):

    transaction = Transaction.query.filter_by(
        id=transaction_id, user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":

        title = request.form.get("title", "").strip()

        category = request.form.get("category", "").strip()

        description = request.form.get("description", "").strip()

        try:

            amount = float(request.form.get("amount", ""))

            if amount <= 0:
                raise ValueError

            transaction_date = datetime.strptime(
                request.form.get("transaction_date", ""), "%Y-%m-%d"
            ).date()

            transaction_type = request.form.get("transaction_type", "")

            if transaction_type not in ["income", "expense"]:
                raise ValueError

            if not title or not category:
                raise ValueError

        except ValueError:

            flash("Please enter valid transaction details.", "danger")

            return redirect(url_for("edit_transaction", transaction_id=transaction.id))

        transaction.title = title

        transaction.amount = amount

        transaction.category = category

        transaction.description = description

        transaction.transaction_type = transaction_type

        transaction.transaction_date = transaction_date

        db.session.commit()

        flash("Transaction updated successfully!", "success")

        return redirect(url_for("transactions"))

    return render_template(
        "add_transaction.html", transaction=transaction, edit_mode=True
    )


# ==========================================
# 12. DELETE TRANSACTION
# ==========================================


@app.route("/delete-transaction/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):

    transaction = Transaction.query.filter_by(
        id=transaction_id, user_id=current_user.id
    ).first_or_404()

    db.session.delete(transaction)

    db.session.commit()

    flash("Transaction deleted successfully.", "success")

    return redirect(url_for("transactions"))


# ==========================================
# 13. BUDGET MANAGEMENT
# ==========================================


@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():

    today = date.today()

    if request.method == "POST":

        category = request.form.get("category", "").strip()

        try:

            amount = float(request.form.get("amount", ""))

            month = int(request.form.get("month", today.month))

            year = int(request.form.get("year", today.year))

            if not category or amount <= 0:
                raise ValueError

            if month < 1 or month > 12 or year < 2000:
                raise ValueError

        except ValueError:

            flash("Please enter valid budget details.", "danger")

            return redirect(url_for("budgets"))

        existing_budget = Budget.query.filter_by(
            user_id=current_user.id, category=category, month=month, year=year
        ).first()

        if existing_budget:

            existing_budget.amount = amount

            flash("Budget updated successfully.", "success")

        else:

            new_budget = Budget(
                category=category,
                amount=amount,
                month=month,
                year=year,
                user_id=current_user.id,
            )

            db.session.add(new_budget)

            flash("Budget created successfully.", "success")

        db.session.commit()

        return redirect(url_for("budgets"))

    all_budgets = (
        Budget.query.filter_by(user_id=current_user.id)
        .order_by(Budget.year.desc(), Budget.month.desc())
        .all()
    )

    budget_data = []

    for budget in all_budgets:

        spent = (
            db.session.query(db.func.sum(Transaction.amount))
            .filter(
                Transaction.user_id == current_user.id,
                Transaction.category == budget.category,
                Transaction.transaction_type == "expense",
                db.extract("month", Transaction.transaction_date) == budget.month,
                db.extract("year", Transaction.transaction_date) == budget.year,
            )
            .scalar()
            or 0
        )

        budget_data.append(
            {
                "budget": budget,
                "spent": spent,
                "remaining": budget.amount - spent,
                "percentage": min((spent / budget.amount) * 100, 100),
            }
        )

    return render_template(
        "budgets.html",
        budget_data=budget_data,
        current_month=today.month,
        current_year=today.year,
    )


@app.route("/savings_goal", methods=["GET", "POST"])
@login_required
def savings_goal():

    if request.method == "POST":

        action = request.form.get("action")

        # Update existing savings goal
        if action == "update_savings":

            goal_id = request.form.get("goal_id", type=int)
            amount_saved = request.form.get("amount_saved", type=float)

            goal = SavingGoal.query.filter_by(
                id=goal_id, user_id=current_user.id
            ).first()

            if goal is None or amount_saved is None or amount_saved < 0:

                flash("Please enter a valid savings amount.", "danger")

            else:

                goal.amount_saved = amount_saved
                db.session.commit()

                flash("Savings progress updated successfully!", "success")

            return redirect(url_for("savings_goal"))

        # Create a new savings goal
        title = request.form.get("title", "").strip()

        try:
            target_amount = float(request.form.get("target_amount", ""))

            if not title or target_amount <= 0:
                raise ValueError

        except ValueError:

            flash("Please enter goal name and a valid target amount.", "danger")

            return redirect(url_for("savings_goal"))

        new_goal = SavingGoal(
            title=title, target_amount=target_amount, user_id=current_user.id
        )

        db.session.add(new_goal)
        db.session.commit()

        flash("Savings goal created successfully!", "success")

        return redirect(url_for("savings_goal"))

    goals = SavingGoal.query.filter_by(user_id=current_user.id).all()

    return render_template("savings_goal.html", goals=goals)


# ==========================================
# 14. DATABASE INITIALIZATION
# ==========================================

with app.app_context():

    db.create_all()

    with db.engine.begin() as connection:

        columns = connection.execute(text("PRAGMA table_info(saving_goal)")).fetchall()

        column_names = [column[1] for column in columns]

        if "amount_saved" not in column_names:

            connection.execute(text("""
                ALTER TABLE saving_goal
                ADD COLUMN amount_saved
                FLOAT NOT NULL DEFAULT 0
                """))


# ==========================================
# 15. RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)
