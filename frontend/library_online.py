import psycopg2
import os
from datetime import datetime
from flask import Flask, render_template, request, url_for, redirect
from db_config import *
# to set FLASK_APP --> $env:FLASK_APP = "library_online.py"
# development mode : $env:FLASK_ENV = "development"
template_dir = os.path.dirname(__file__)
template_dir = os.path.join(template_dir, 'template')

# due of borrowing
due_day = 7

app = Flask(__name__, template_folder=template_dir)

def connect_db():
    conn = psycopg2.connect(host=db_host,
                    database=db_name, user=db_user, password=db_pw) # remember to hide credentails
    return conn

@app.route('/')
def index():
    # get database connecton
    conn = connect_db()
    #conn.autocommit = True
    # create a cursor
    cur = conn.cursor()
        
    # execute a statement
    cur.execute(f"SELECT * FROM book NATURAL JOIN \
        (SELECT COUNT(return_date) AS total_borrows,book_id FROM record GROUP BY book_id) AS count_borrow  \
        ORDER BY total_borrows DESC\
        LIMIT 10")
    books = cur.fetchall()
    # close the communication with the PostgreSQL
    cur.close()
    conn.close()

    return render_template('index.html', books=books)

# search for books with key words, display its details
@app.route('/search/',methods=('GET','POST'))
def search():
    conn = connect_db()
    cur = conn.cursor()

    if request.method=='POST':
        # search key fetch
        search_key = request.form['search_key']
        # book information
        cur.execute(f"SELECT * FROM book LEFT JOIN \
        (SELECT COUNT(return_date),book_id FROM record GROUP BY book_id) AS count_borrow  \
        ON book.book_id = count_borrow.book_id  \
        WHERE name_ LIKE '%%{search_key}%%' LIMIT 10")
        search_result = cur.fetchall()
        #print(search_result)
        # number of borrowed times
        conn.close()
        cur.close()
        return render_template('search.html',search_results=search_result)
    conn.close()
    cur.close()
    return render_template('search.html')
        
"""
example user:
('goverment_q', '815722453'), ('LevityNYC', '815722454'), ('VertigoOfCal', '815722455'), 
('9DEBORA5Tracy05', '815722456'), ('ABB8C2', '815722457'), ('fiftharirection', '815722460'), 
('NHMS', '815722462'), ('sumeyrahx', '815722463'), ('NewsNeus', '815722464')
"""
# borrow a book
@app.route('/borrow/', methods=('GET','POST'))
def create():
    conn = connect_db()
    cur = conn.cursor()
    # borrow log
    cur.execute('SELECT book_id, user_.name_, borrow_date FROM borrowed_by,user_ \
                    WHERE borrowed_by.user_id = user_.user_id\
                     ORDER BY borrow_date DESC LIMIT 3')
    borrows = cur.fetchall()
    # if user write the form
    if request.method == 'POST':
        book_id = request.form['book_id']
        user_name = request.form['user_name']
        user_pw = request.form['user_pw']
        borrow_date = str(datetime.now())[0:19]
        # check if the book and the user exist
        cur.execute(f"SELECT * FROM book WHERE book_id = '{book_id}'")
        borrowed_book = cur.fetchone()
        cur.execute(f"SELECT name_, user_id FROM user_ WHERE name_ = '{user_name}' AND user_id = '{user_pw}'")
        borrower = cur.fetchone()
        # if wrong input, output error line
        if borrowed_book is None:
            return render_template('borrow.html', borrows=borrows, error="Invalid book id")
        elif borrowed_book[-1] != '1':
            return render_template('borrow.html', borrows=borrows, error="This book is borrowed away")
        if borrower is None:
            return render_template('borrow.html', borrows=borrows, error="Please check your name or password")
        
        try:
            # insert
            cur.execute('INSERT INTO borrowed_by (book_id, user_id, borrow_date)'
                        f"VALUES ('{book_id}', '{user_pw}', '{borrow_date}')")
            # update as borrowed
            cur.execute(f"UPDATE book SET available = \'0\' WHERE book_id = '{book_id}'")
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('create'))
        
        # invalid inputs
        except psycopg2.Error as e:
            conn.rollback()
            return render_template('borrow.html', borrows=borrows, error=e)
        
    cur.close()
    conn.close()
    return render_template('borrow.html', borrows=borrows)

# return a book
@app.route('/return/', methods=('GET','POST'))
def return_():
    conn = connect_db()
    cur = conn.cursor()
    # borrow log
    cur.execute('SELECT book_id, user_.name_, return_date FROM record, user_\
                WHERE record.user_id = user_.user_id\
                ORDER BY return_date DESC LIMIT 3')
    returns = cur.fetchall()
    # if user write the form
    if request.method == 'POST':
        book_id = request.form['book_id']
        user_name = request.form['user_name']
        user_pw = request.form['user_pw']
        return_date = str(datetime.now())[0:19]
        # check if the book and the user exist
        cur.execute(f"SELECT * FROM book WHERE book_id = '{book_id}'")
        returned_book = cur.fetchone()
        # check if valid user
        cur.execute(f"SELECT name_, user_id FROM user_ WHERE name_ = '{user_name}' AND user_id = '{user_pw}'")
        returner = cur.fetchone()
        # check if this user really borrowed this book
        cur.execute(f"SELECT * FROM borrowed_by WHERE book_id = '{book_id}' AND user_id = '{user_pw}'")
        check_borrow = cur.fetchone()
        # if wrong input, output error line
        if returned_book is None:
            return render_template('return.html', returns=returns, error="Invalid book id")
        if returner is None:
            return render_template('return.html', returns=returns, error="Please check your name or password")
        # if this user did not borrow
        if check_borrow is None:
            return render_template('return.html', returns=returns, error="You did not borrowed this book!")
        
        try:
            # remove the borrowed row
            cur.execute(f"DELETE FROM borrowed_by WHERE book_id = '{book_id}' RETURNING *")         #(book_id,user_name,return_date))
            returned_item = cur.fetchone()
            # insert to record table
            cur.execute('INSERT INTO record (book_id, user_id, borrow_date, return_date)'
                        f"VALUES ('{book_id}', '{user_pw}', '{returned_item[-1]}', '{return_date}')")#book_id,user_name,returned_item[-1],return_date))
            # update as returned
            cur.execute(f"UPDATE book SET available = \'1\' WHERE book_id = '{book_id}'")
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('return_'))
        
        # invalid inputs
        except psycopg2.Error as e:
            conn.rollback()
            return render_template('return.html', returns=returns, error=e)
        #return redirect(url_for('confirm_create',bb=borrowed_book, bd=borrow_date))
    cur.close()
    conn.close()
    return render_template('return.html', returns=returns)

# user profile
@app.route('/profile/',methods=('GET','POST'))
def profile():
    conn = connect_db()
    cur = conn.cursor()
    if request.method=='POST':
        # user information
        user_nm = request.form['user_nm']
        user_pw = request.form['user_pw']
        # check if valid user
        cur.execute('SELECT * FROM user_ WHERE name_ = %s AND user_id = %s',(user_nm,user_pw))
        user = cur.fetchone()
        # if not valid
        if user is None:
            conn.close()
            cur.close()
            return render_template('profile.html', error="Please check your name or password")
        # send profile back
        else:
            # borrowing books
            cur.execute(f"SELECT * FROM borrowed_by NATURAL JOIN book WHERE user_id = '{user_pw}' LIMIT 10")
            borrowing_books = cur.fetchall() 
            # borrowing count
            cur.execute(f"SELECT * FROM \
            (SELECT COUNT(borrow_date) AS borrow_count, user_id  FROM borrowed_by GROUP BY user_id) AS borrow_counts\
            WHERE user_id = '{user_pw}'")
            borrowing_count = cur.fetchone()
            # current date to calculate how many days left before due
            date = str(datetime.now())
            year = int(date[0:4])
            month = int(date[5:7])
            day = int(date[8:10])
            # calculate borrow day
            for i in range(len(borrowing_books)):
                bb = list(borrowing_books[i])
                b_date = bb[2]
                b_year = int(b_date[0:4])
                b_month = int(b_date[5:7])
                b_day = int(b_date[8:10])
                left_date =  due_day - (year*365 + month*31 + day) + (b_year*365 + b_month*31 + b_day)
                bb.append(left_date)
                borrowing_books[i] = tuple(bb)
            # borrowed history
            cur.execute(f"SELECT * FROM record NATURAL JOIN book WHERE user_id = '{user_pw}'")
            borrowed_record = cur.fetchmany(10)
            # borrowed count
            cur.execute(f"SELECT * FROM \
            (SELECT COUNT(return_date) AS borrow_count, user_id  FROM record GROUP BY user_id) AS borrow_counts\
            WHERE user_id = '{user_pw}'")
            borrowed_count = cur.fetchone()

            return render_template('profile.html',profile=user,bb=borrowing_books,bc=borrowing_count,
                                    bb2=borrowed_record,bc2=borrowed_count)
            
    conn.close()
    cur.close()
    return render_template('profile.html')

