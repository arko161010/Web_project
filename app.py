from flask import Flask, render_template, redirect, url_for, session, flash, request, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField
from wtforms.validators import DataRequired, Email, ValidationError
import bcrypt
import psycopg2
from psycopg2.extras import DictCursor
from agent import (
    extract_text_from_pdf,
    generate_combined_response,
    load_user_conversation_history,
    save_user_conversation_history,
)
from dotenv import load_dotenv
import os

app = Flask(__name__)

# Load environment variables
load_dotenv()

# # PostgreSQL Configuration
# app.config['DB_HOST'] = os.getenv('DB_HOST')
# app.config['DB_NAME'] = os.getenv('DB_NAME')
# app.config['DB_USER'] = os.getenv('DB_USER')
# app.config['DB_PASSWORD'] = os.getenv('DB_PASSWORD')
# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# PostgreSQL Configuration
app.config['DB_HOST'] = "127.0.0.1"
app.config['DB_NAME'] = "admission_ai"
app.config['DB_USER'] = "postgres"
app.config['DB_PASSWORD'] = "12345"
app.config['SECRET_KEY'] = "super_secret_key_12345"


def get_db_connection():
    return psycopg2.connect(
        host=app.config['DB_HOST'],
        database=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD']
    )

class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

    def validate_email(self, field):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (field.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            raise ValidationError('Email Already Taken')

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class AdmissionForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[DataRequired()])
    dob = DateField("Date of Birth", format='%Y-%m-%d', validators=[DataRequired()])
    department = SelectField("Department", choices=[
        ("CSE", "Computer Science and Engineering (CSE)"),
        ("EEE", "Electrical and Electronic Engineering (EEE)"),
        ("BBA", "Bachelor of Business Administration (BBA)"),
        ("SWE", "Software Engineering (SWE)"),
        ("ENG", "English")
    ], validators=[DataRequired()])
    ssc_result = StringField("SSC GPA", validators=[DataRequired()])
    hsc_result = StringField("HSC GPA", validators=[DataRequired()])
    submit = SubmitField("Submit Application")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password.decode('utf-8')))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            session['user_id'] = user[0]
            return redirect(url_for('dashboard'))
        else:
            flash("Login failed. Please check your email and password")
            return redirect(url_for('login'))

    return render_template('login.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        user_id = session['user_id']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            return render_template('dashboard.html', user=user)

    return redirect(url_for('login'))

@app.route('/info')
def info():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)

    # Fetch user
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    # Fetch application
    cursor.execute("SELECT * FROM applications WHERE user_id = %s", (user_id,))
    application = cursor.fetchone()

    cursor.close()
    conn.close()

    if application:
        return render_template('info.html', application=application, user=user)
    else:
    
        return render_template('info.html')
        

@app.route('/apply', methods=['GET', 'POST'])
def apply():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    form = AdmissionForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO applications 
            (full_name, email, phone, dob, department, ssc_result, hsc_result, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            form.full_name.data,
            form.email.data,
            form.phone.data,
            form.dob.data,
            form.department.data,
            form.ssc_result.data,
            form.hsc_result.data,
            session['user_id']
        ))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Application submitted successfully", "success")
        return redirect(url_for('dashboard'))
    
    return render_template('apply.html', form=form)


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    # Check if the user is logged in, otherwise assign 'guest' as the user ID
    user_id = session.get('user_id', None)

    if request.method == 'POST':
        try:
            pdf_data = extract_text_from_pdf("DIU.pdf")

            # For guest users, do not load or save history
            if user_id:
                chat_history = load_user_conversation_history(user_id)
            else:
                chat_history = []

            user_input = request.json["message"]
            chat_history.append({"role": "user", "message": user_input})

            response = generate_combined_response(pdf_data, user_input, chat_history)

            chat_history.append({"role": "assistant", "message": response})

            # Save history only for logged-in users
            if user_id:
                save_user_conversation_history(user_id, chat_history)

            return jsonify({"reply": response})
        except Exception as e:
            print("Error in Chat:", e)
            return jsonify({"error": str(e)}), 500

    # For guest users, do not load history
    chat_history = load_user_conversation_history(user_id) if user_id else []
    return render_template('chat.html', chat_history=chat_history)


@app.route('/payment')
def payment():
    if 'user_id' in session:
        user_id = session['user_id']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            return render_template('payment.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out successfully.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)