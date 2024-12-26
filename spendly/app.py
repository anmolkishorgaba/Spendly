from flask import Flask, request, render_template, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField, DateField
from wtforms.validators import InputRequired, Length, EqualTo
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///spendly.db'
app.config['SECRET_KEY'] = 'supersecret'
db = SQLAlchemy()
db.init_app(app)
bcrypt = Bcrypt(app)
app.app_context().push()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return UsersTable.query.get(int(user_id))

# TABLE MODELS ----------------------------------------------------------------------------------------------------------------
class AccountsTable(db.Model):
    def __init__(self, uid, acn, ty, bank, bal, mbal):
        self.userid = uid
        self.accno = acn
        self.type = ty
        self.bank = bank 
        self.balance = bal
        self.minbal = mbal
    __tablename__ = 'accounts'
    accno = db.Column(db.String, primary_key = True)
    userid = db.Column(db.Integer, db.ForeignKey("users.id", ondelete='CASCADE'), nullable = False)
    type = db.Column(db.String, nullable = False)
    bank = db.Column(db.String, nullable = False)
    balance = db.Column(db.Integer, nullable = False, default=0)
    minbal = db.Column(db.Integer, default=0)

class TransactionsTable(db.Model):
    def __init__(self, uid, date, acn, type, amnt, cat):
        self.userid = uid
        self.date = date
        self.accno = acn
        self.type = type
        self.amount = amnt
        self.category = cat
    __tablename__ = 'transactions'
    tno = db.Column(db.Integer, primary_key = True, autoincrement = True)
    userid = db.Column(db.Integer, db.ForeignKey("users.id", ondelete='CASCADE'), nullable = False)
    date = db.Column(db.String, nullable = False)
    accno = db.Column(db.Integer, db.ForeignKey("accounts.accno"), nullable = False)
    type = db.Column(db.String, nullable = False)
    amount = db.Column(db.Integer, nullable = False)
    category = db.Column(db.String)

class UsersTable(db.Model, UserMixin):
    def __init__(self, uname, pwd):
        self.username = uname
        self.password = pwd
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String, nullable = False, unique = True)
    password = db.Column(db.Integer, nullable = False)

class CashTable(db.Model, UserMixin):
    def __init__(self, uid, bal=0):
        self.userid = uid
        self.balance = bal
    __tablename__ = 'cash'
    uid = db.Column(db.Integer, primary_key = True)
    balance = db.Column(db.Integer, nullable = False)

# Forms -----------------------------------------------------------------------------------------------------------------------

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Login')

class AccountForm(FlaskForm):
    account_number = StringField('Account Number', validators=[InputRequired()] )
    type = SelectField('Account Type',choices=[('', 'Select Account Type'), ('savings', 'Savings Account'), ('current', 'Current Account')] ,validators=[InputRequired()])
    bank = StringField('Bank Name', validators=[InputRequired()])
    balance = IntegerField('Current Balance', validators=[InputRequired()])
    minimum_balance = IntegerField('Minimum Balance')
    submit = SubmitField('Add Account')

class TransactionForm(FlaskForm):
    categories = [
        ("", "Select Category"),
        ("Rent", "Rent"),
        ("Salary", "Salary"),
        ("Utilities", "Utilities"),
        ("Transportation", "Transportation"),
        ("Food", "Food"),
        ("Health & Insurance", "Health & Insurance"),
        ("Entertainment", "Entertainment"),
        ("Savings & Investments", "Savings & Investments"),
        ("Debt Repayment", "Debt Repayment"),
        ("Miscellaneous", "Miscellaneous")
    ]
    account_number = SelectField("Account Number", validators=[InputRequired()])
    amount = IntegerField('Amount', validators=[InputRequired()])
    type = SelectField('Type', choices=[('', "Select Type"), ('expense', "Expenditure"), ('income', "Income")],validators=[InputRequired()])
    date = DateField('Date', default=datetime.today(), validators=[InputRequired()])
    category = SelectField('Category', choices=categories)
    submit = SubmitField('Add Transaction')

# Routes ----------------------------------------------------------------------------------------------------------------------

@app.route("/", methods = ["GET", "POST"])
@login_required
def index():
    transactions = TransactionsTable.query.filter_by(userid=current_user.id).order_by(TransactionsTable.date.desc(), TransactionsTable.tno.desc()).all()
    total = sum([i.balance for i in AccountsTable.query.filter_by(userid=current_user.id).all()]) + CashTable.query.get(current_user.id).balance
    monthly_income = sum([i.amount if i.type == 'income' else 0 for i in TransactionsTable.query.filter(
        TransactionsTable.userid == current_user.id,
        TransactionsTable.date >= datetime.now() - timedelta(days=30)
    ).all()])
    monthly_expenditure = sum([i.amount if i.type == 'expense' else 0 for i in TransactionsTable.query.filter(
        TransactionsTable.userid == current_user.id,
        TransactionsTable.date >= datetime.now() - timedelta(days=30)
    ).all()])

    return render_template("index.html", recent=transactions[:8], total=total, monthly_earnings=monthly_income, monthly_expenditure=monthly_expenditure, title='Dashboard', transactions=transactions)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if UsersTable.query.filter_by(username=form.username.data).first():
        flash('Username already taken, pick a new one.', 'danger')
    if form.password.data != form.confirm_password.data:
        flash('Please enter the same password in confirm password.', 'danger')
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = UsersTable(form.username.data, hashed_password)
        cash = CashTable(form.username.data)
        db.session.add(user)
        db.session.add(cash)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods = ["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = UsersTable.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form, title='Login')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/accounts', methods = ["GET", "POST"])
@login_required
def accounts():
    form = AccountForm()
    if form.is_submitted():
        if AccountsTable.query.filter_by(accno=form.account_number.data).first():
            flash("Account number is already registered by you or another user.", "danger")
        else:
            acc = AccountsTable(
                uid=current_user.id,
                acn=form.account_number.data,
                ty=form.type.data,
                bank=form.bank.data,
                bal=form.balance.data,
                mbal=form.minimum_balance.data if form.minimum_balance.data else 0
            )
            db.session.add(acc)
            db.session.commit()
            flash("Account added successfully.", "success")
            return redirect(url_for('accounts'))
        
    accounts = AccountsTable.query.filter_by(userid=current_user.id).all()
    cash = CashTable.query.get(current_user.id).balance
    return render_template('accounts.html', form=form, accounts=accounts, cash=cash, title='Accounts')

@app.route('/accountpage/<int:accno>', methods = ["GET", "POST"])
@login_required
def accountpage(accno):
    acc = AccountsTable.query.get(accno)
    if acc.userid == current_user.id:
        transactions = TransactionsTable.query.filter_by(accno=accno).order_by(TransactionsTable.date.desc(), TransactionsTable.tno.desc()).all()
        return render_template("accountpage.html", account=acc, transactions=transactions, title='Account')
    else:
        flash("You dont own this account.", "danger")
        return redirect("/")
    
@app.route('/delete/<int:accno>', methods = ["GET", "POST"])
@login_required
def delete(accno):
    acc = AccountsTable.query.get(accno)
    if acc.userid == current_user.id:
        db.session.delete(acc)
        db.session.commit()
        flash("Account deleted successfully.", "success")
        return redirect(url_for('accounts'))
    else:
        flash("You dont own this account.", "danger")
        return redirect("/")

@app.route('/transactions', methods = ["GET", "POST"])
@login_required
def transactions():
    form = TransactionForm()
    if form.is_submitted():
        if form.date.data > datetime.today().date():
            flash("Date can't be of after current date.", "danger")
            return redirect(url_for("transactions"))
        if form.account_number.data == 'cash':
            cash = CashTable.query.get(current_user.id)
            if form.type.data == 'expense':
                if form.amount.data > cash.balance:
                    flash("Insufficient cash balance.", "danger")
                    return redirect(url_for("transactions"))
                else:
                    cash.balance -= form.amount.data
            elif form.type.data == 'income':
                cash.balance += form.amount.data
        else: 
            acc = AccountsTable.query.get(form.account_number.data)
            if form.type.data == 'expense':
                if form.amount.data > acc.balance:
                    flash("Insufficient balance in that account.", "danger")
                    return redirect(url_for("transactions"))
                else:
                    acc.balance -= form.amount.data
            elif form.type.data == 'income':
                acc.balance += form.amount.data

        transaction = TransactionsTable(
            uid = current_user.id,
            date = form.date.data,
            acn = form.account_number.data,
            type = form.type.data,
            amnt = form.amount.data,
            cat = form.category.data
        )
        db.session.add(transaction)
        db.session.commit()
        flash("Transaction successfull.", "success")
        return redirect(url_for("transactions"))
    transactions = TransactionsTable.query.filter_by(userid=current_user.id).order_by(TransactionsTable.date.desc(), TransactionsTable.tno.desc()).all()
    
    form.account_number.choices = [('', "Choose Account"), ('cash', "Cash")] + [(i.accno, f"{i.accno} - {i.bank}") for i in AccountsTable.query.filter_by(userid=current_user.id).all()]
    return render_template('transactions.html', form=form, transactions=transactions, title="Transactions")




# Main ------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    db.create_all()
    app.run(debug=True)
