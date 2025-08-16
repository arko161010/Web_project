from flask import Flask, render_template, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, ValidationError
import bcrypt
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import os

app = Flask(__name__,  template_folder="templates1")

# Load environment variables
load_dotenv()

# PostgreSQL Configuration
app.config['DB_HOST'] = os.getenv('DB_HOST')
app.config['DB_NAME'] = os.getenv('DB_NAME')
app.config['DB_USER'] = os.getenv('DB_USER')
app.config['DB_PASSWORD'] = os.getenv('DB_PASSWORD')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')


def get_db_connection():
    return psycopg2.connect(
        host=app.config['DB_HOST'],
        database=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD']
    )


# Forms
class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    admin_id = StringField("Admin ID", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

    def validate_admin_id(self, field):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (field.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            raise ValidationError('Admin ID already taken.')


class LoginForm(FlaskForm):
    admin_id = StringField("Admin ID", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


# Home Page Route
@app.route('/')
def ind():
    return render_template('ind.html')


# Registration Route
@app.route('/reg', methods=['GET', 'POST'])
def reg():
    form = RegisterForm()
    if form.validate_on_submit():
        name = form.name.data
        admin_id = form.admin_id.data
        password = form.password.data

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO admin (name, admin_id, password) VALUES (%s, %s, %s)",
                       (name, admin_id, hashed_password.decode('utf-8')))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for('log'))

    return render_template('reg.html', form=form)


# Login Route
@app.route('/log', methods=['GET', 'POST'])
def log():
    form = LoginForm()
    if form.validate_on_submit():
        admin_id = form.admin_id.data
        password = form.password.data

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            session['user_id'] = user[0]
            flash("Login successful.", "success")
            return redirect(url_for('dash'))
        else:
            flash("Login failed. Please check your Admin ID and password.", "danger")

    return render_template('log.html', form=form)


# Dashboard Route
@app.route('/dash')
def dash():
    if 'user_id' in session:
        user_id = session['user_id']

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT * FROM admin WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            return render_template('dash.html', user=user)

    return redirect(url_for('log'))


# Application Info Route
@app.route('/student')
def student():
    if 'user_id' not in session:
        return redirect(url_for('log'))

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)

    # Fetch user info
    cursor.execute("SELECT * FROM admin WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    # Fetch related application(s)
    cursor.execute("SELECT * FROM applications WHERE user_id = %s", (user_id,))
    applications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('student.html', user=user, applications=applications)


# Logout Route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('log'))


# Main Entry Point
if __name__ == '__main__':
    app.run(debug=True, port=50001)
