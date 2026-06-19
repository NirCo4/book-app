from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'books-store-2026'

DB_PATH = os.path.join(os.path.dirname(__file__), 'books.db')

# Kept for fallback ordering in legacy reports
BOOKS = [
    'סופרות בטרם עת', 'גן עדן לחתולים', 'קמצנים, חמדנים, עסקנים',
    'שני סיפורים נודדים', 'מקאריו', 'דרכים חלופיות', 'עץ הקיפודים',
    'משחק הגורלות', 'גרוסמן', 'ביאליק', 'דוסטויבסקי', 'בלזק',
    'כללי (משותף לסדרה)'
]

MONTHS = [
    '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06',
    '2026-07', '2026-08', '2026-09', '2026-10', '2026-11', '2026-12',
    '2027-01', '2027-02', '2027-03', '2027-04', '2027-05', '2027-06',
]

STATUSES = ['תכנון', 'תזרים', 'חשבונאי']
TYPES = ['הוצאה', 'הכנסה']

ITEMS = [
    'זכויות', 'תרגום', 'עריכה', 'הגהה', 'עימוד', 'עיצוב גלויות',
    'כתיבת גב וביוגרפיה', 'עיצוב כריכה', 'דפוס', 'גלויות', 'משלוחי יח"צ',
    'שיווק / יח״צ', 'הפצה / עמלות', 'חומרי אריזה', 'שילוח', 'משלוחים',
    'אחסון', 'איור כריכה', 'חנויות', 'איורים (פנים)', 'מעמדי עץ',
    'מוסדות / ארגונים', 'חו״ל', 'אירועים / הרצאות', 'מכירות באתר',
    'מכירות בחנויות', 'אחרות (הכנסה)'
]

MONTH_LABELS = {
    '2026-01': 'ינואר 2026', '2026-02': 'פברואר 2026', '2026-03': 'מרץ 2026',
    '2026-04': 'אפריל 2026', '2026-05': 'מאי 2026', '2026-06': 'יוני 2026',
    '2026-07': 'יולי 2026', '2026-08': 'אוגוסט 2026', '2026-09': 'ספטמבר 2026',
    '2026-10': 'אוקטובר 2026', '2026-11': 'נובמבר 2026', '2026-12': 'דצמבר 2026',
    '2027-01': 'ינואר 2027', '2027-02': 'פברואר 2027', '2027-03': 'מרץ 2027',
    '2027-04': 'אפריל 2027', '2027-05': 'מאי 2027', '2027-06': 'יוני 2027',
}

BOOK_STATUSES = ['טיוטה', 'בייצור', 'יצא לאור', 'אזל']
PRODUCTION_STAGES_LIST = ['כתב יד', 'עריכה', 'הגהה', 'עימוד', 'עיצוב כריכה', 'דפוס', 'הפצה']
PRODUCTION_STATUSES = ['ממתין', 'בתהליך', 'הושלם', 'עיכוב']
AUTHOR_ROLES = ['מחבר', 'מחברת', 'מתרגם', 'מתרגמת', 'מאייר', 'מאיירת', 'עורך', 'עורכת']


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def status_filter_sql(status_filter):
    if status_filter == 'תכנון':
        return "status = 'תכנון'"
    elif status_filter == 'בפועל':
        return "status != 'תכנון'"
    return '1=1'


def get_books_list():
    """Return active book titles from DB for dropdowns."""
    try:
        db = get_db()
        rows = db.execute(
            "SELECT title FROM books WHERE status != 'טיוטה' ORDER BY title"
        ).fetchall()
        db.close()
        return [r['title'] for r in rows] or BOOKS
    except Exception:
        return BOOKS


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        db.close()
        if user and check_password_hash(user['password_hash'], password):
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        flash('שם משתמש או סיסמה שגויים', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Users ─────────────────────────────────────────────────────────────────────

@app.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    db = get_db()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('יש למלא שם משתמש וסיסמה', 'danger')
        elif db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
            flash(f'המשתמש "{username}" כבר קיים', 'danger')
        else:
            db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                       (username, generate_password_hash(password)))
            db.commit()
            flash(f'המשתמש "{username}" נוסף בהצלחה', 'success')
    all_users = db.execute('SELECT id, username FROM users ORDER BY username').fetchall()
    db.close()
    return render_template('users.html', users=all_users)


@app.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
def delete_user(uid):
    db = get_db()
    user = db.execute('SELECT username FROM users WHERE id=?', (uid,)).fetchone()
    if user and user['username'] == session['username']:
        flash('לא ניתן למחוק את המשתמש הנוכחי', 'danger')
    elif user:
        db.execute('DELETE FROM users WHERE id=?', (uid,))
        db.commit()
        flash(f'המשתמש "{user["username"]}" נמחק', 'warning')
    db.close()
    return redirect(url_for('users'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    status = request.args.get('status', 'כל')
    sf = status_filter_sql(status)
    db = get_db()

    totals = db.execute(f'''
        SELECT
            COALESCE(SUM(CASE WHEN type="הכנסה" THEN amount_accounting ELSE 0 END), 0) AS total_income,
            COALESCE(SUM(CASE WHEN type="הוצאה" THEN amount_accounting ELSE 0 END), 0) AS total_expenses,
            COALESCE(SUM(amount_accounting), 0) AS net
        FROM transactions WHERE {sf}
    ''').fetchone()

    monthly = db.execute(f'''
        SELECT month,
            COALESCE(SUM(CASE WHEN type="הכנסה" THEN amount_accounting ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type="הוצאה" THEN amount_accounting ELSE 0 END), 0) AS expenses,
            COALESCE(SUM(amount_accounting), 0) AS net
        FROM transactions WHERE {sf}
        GROUP BY month ORDER BY month
    ''').fetchall()

    cumulative = 0
    trough = 0
    trough_month = None
    monthly_with_cum = []
    for row in monthly:
        cumulative += row['net']
        if cumulative < trough:
            trough = cumulative
            trough_month = row['month']
        monthly_with_cum.append({
            'month': row['month'],
            'label': MONTH_LABELS.get(row['month'], row['month']),
            'income': row['income'],
            'expenses': row['expenses'],
            'net': row['net'],
            'cumulative': cumulative,
        })

    db.close()
    return render_template('dashboard.html',
        totals=totals, monthly=monthly_with_cum,
        trough=trough, trough_month=MONTH_LABELS.get(trough_month, trough_month or '—'),
        status=status, month_labels=MONTH_LABELS)


# ── Data Entry ────────────────────────────────────────────────────────────────

@app.route('/entry', methods=['GET', 'POST'])
@login_required
def entry():
    if request.method == 'POST':
        month = request.form.get('month', '').strip()
        book = request.form.get('book', '').strip()
        status = request.form.get('status', '').strip()
        ttype = request.form.get('type', '').strip()
        item = request.form.get('item', '').strip()
        amount_str = request.form.get('amount', '').strip()
        notes = request.form.get('notes', '').strip()

        errors = []
        if not month:   errors.append('יש לבחור חודש')
        if not book:    errors.append('יש לבחור ספר')
        if not status:  errors.append('יש לבחור סטטוס')
        if not ttype:   errors.append('יש לבחור סוג תנועה')
        if not item:    errors.append('יש לבחור פריט')
        try:
            amount = float(amount_str) if amount_str else None
            if amount is None or amount <= 0:
                errors.append('יש להזין סכום חיובי')
        except ValueError:
            errors.append('סכום לא תקין')
            amount = None

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            accounting = amount if ttype == 'הכנסה' else -amount
            db = get_db()
            db.execute('''
                INSERT INTO transactions
                    (month, book, status, type, item, amount_positive, amount_accounting, notes, entered_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (month, book, status, ttype, item, amount, accounting,
                  notes or None, session['username']))
            db.commit()
            db.close()
            flash('הרשומה נשמרה בהצלחה', 'success')
            return redirect(url_for('entry'))

    page = max(1, request.args.get('page', 1, type=int))
    per_page = 50
    offset = (page - 1) * per_page
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
    recent = db.execute(
        'SELECT * FROM transactions ORDER BY id DESC LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()
    db.close()
    total_pages = (total + per_page - 1) // per_page
    return render_template('entry.html',
        books=get_books_list(), months=MONTHS, statuses=STATUSES, types=TYPES,
        items=ITEMS, recent=recent, month_labels=MONTH_LABELS,
        page=page, total_pages=total_pages)


@app.route('/entry/<int:tid>/edit', methods=['GET', 'POST'])
@login_required
def edit_entry(tid):
    db = get_db()
    row = db.execute('SELECT * FROM transactions WHERE id=?', (tid,)).fetchone()
    if not row:
        db.close()
        flash('רשומה לא נמצאה', 'danger')
        return redirect(url_for('entry'))

    if request.method == 'POST':
        month = request.form.get('month', '').strip()
        book = request.form.get('book', '').strip()
        status = request.form.get('status', '').strip()
        ttype = request.form.get('type', '').strip()
        item = request.form.get('item', '').strip()
        amount_str = request.form.get('amount', '').strip()
        notes = request.form.get('notes', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            flash('סכום לא תקין', 'danger')
            return render_template('entry_edit.html', row=row,
                books=get_books_list(), months=MONTHS, statuses=STATUSES,
                types=TYPES, items=ITEMS, month_labels=MONTH_LABELS)

        accounting = amount if ttype == 'הכנסה' else -amount
        db.execute('''
            UPDATE transactions
            SET month=?, book=?, status=?, type=?, item=?,
                amount_positive=?, amount_accounting=?, notes=?
            WHERE id=?
        ''', (month, book, status, ttype, item, amount, accounting, notes or None, tid))
        db.commit()
        db.close()
        flash('הרשומה עודכנה בהצלחה', 'success')
        return redirect(url_for('entry'))

    db.close()
    return render_template('entry_edit.html', row=row,
        books=get_books_list(), months=MONTHS, statuses=STATUSES,
        types=TYPES, items=ITEMS, month_labels=MONTH_LABELS)


@app.route('/entry/<int:tid>/delete', methods=['POST'])
@login_required
def delete_entry(tid):
    db = get_db()
    db.execute('DELETE FROM transactions WHERE id=?', (tid,))
    db.commit()
    db.close()
    flash('הרשומה נמחקה', 'warning')
    return redirect(url_for('entry'))


# ── Monthly Summary ───────────────────────────────────────────────────────────

@app.route('/monthly')
@login_required
def monthly():
    status = request.args.get('status', 'כל')
    sf = status_filter_sql(status)
    db = get_db()

    rows = db.execute(f'''
        SELECT month,
            COALESCE(SUM(CASE WHEN type="הכנסה" THEN amount_accounting ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type="הוצאה" THEN amount_accounting ELSE 0 END), 0) AS expenses,
            COALESCE(SUM(amount_accounting), 0) AS net
        FROM transactions WHERE {sf}
        GROUP BY month ORDER BY month
    ''').fetchall()

    cf_rows = db.execute('''
        SELECT month,
            COALESCE(SUM(CASE WHEN type="הכנסה" THEN amount_accounting ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type="הוצאה" THEN amount_accounting ELSE 0 END), 0) AS expenses,
            COALESCE(SUM(amount_accounting), 0) AS net
        FROM transactions WHERE status="תזרים"
        GROUP BY month ORDER BY month
    ''').fetchall()

    db.close()

    def with_cumulative(rows):
        out = []
        cum = 0
        for r in rows:
            cum += r['net']
            out.append({'month': r['month'], 'label': MONTH_LABELS.get(r['month'], r['month']),
                        'income': r['income'], 'expenses': r['expenses'],
                        'net': r['net'], 'cumulative': cum})
        return out

    return render_template('monthly.html',
        accounting=with_cumulative(rows),
        cashflow=with_cumulative(cf_rows),
        status=status)


# ── Book Summary ──────────────────────────────────────────────────────────────

@app.route('/book-summary')
@login_required
def book_summary():
    status = request.args.get('status', 'כל')
    sf = status_filter_sql(status)
    db = get_db()
    rows = db.execute(f'''
        SELECT book,
            COALESCE(SUM(CASE WHEN type="הכנסה" THEN amount_accounting ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type="הוצאה" THEN amount_accounting ELSE 0 END), 0) AS expenses,
            COALESCE(SUM(amount_accounting), 0) AS net
        FROM transactions WHERE {sf}
        GROUP BY book ORDER BY book
    ''').fetchall()
    db.close()

    total_income = sum(r['income'] for r in rows)
    total_expenses = sum(r['expenses'] for r in rows)
    total_net = sum(r['net'] for r in rows)

    return render_template('book_summary.html',
        rows=rows, status=status,
        total_income=total_income, total_expenses=total_expenses, total_net=total_net)


# ── Matrix ────────────────────────────────────────────────────────────────────

@app.route('/matrix')
@login_required
def matrix():
    status = request.args.get('status', 'כל')
    view = request.args.get('view', 'נטו')
    sf = status_filter_sql(status)

    if view == 'הכנסות':
        agg = 'SUM(CASE WHEN type="הכנסה" THEN amount_accounting ELSE 0 END)'
    elif view == 'הוצאות':
        agg = 'SUM(CASE WHEN type="הוצאה" THEN amount_accounting ELSE 0 END)'
    else:
        agg = 'SUM(amount_accounting)'

    db = get_db()
    rows = db.execute(f'''
        SELECT book, month, COALESCE({agg}, 0) AS value
        FROM transactions WHERE {sf}
        GROUP BY book, month
    ''').fetchall()

    db_books = [r['title'] for r in db.execute(
        'SELECT title FROM books ORDER BY title'
    ).fetchall()]
    db.close()

    books_order = db_books or BOOKS
    data_months = sorted({r['month'] for r in rows})
    use_months = [m for m in MONTHS if m in data_months] or data_months

    pivot = {}
    for r in rows:
        pivot.setdefault(r['book'], {})[r['month']] = r['value']

    matrix_rows = []
    seen = set()
    for book in books_order:
        if book in pivot:
            seen.add(book)
            month_vals = [pivot.get(book, {}).get(m, 0) for m in use_months]
            matrix_rows.append({'book': book, 'vals': month_vals, 'total': sum(month_vals)})
    for book in pivot:
        if book not in seen:
            month_vals = [pivot.get(book, {}).get(m, 0) for m in use_months]
            matrix_rows.append({'book': book, 'vals': month_vals, 'total': sum(month_vals)})

    col_totals = [sum(r['vals'][i] for r in matrix_rows) for i in range(len(use_months))]
    grand_total = sum(col_totals)

    return render_template('matrix.html',
        months=use_months, month_labels=MONTH_LABELS,
        rows=matrix_rows, col_totals=col_totals, grand_total=grand_total,
        status=status, view=view)


# ── Catalog ───────────────────────────────────────────────────────────────────

@app.route('/catalog')
@login_required
def catalog():
    db = get_db()
    q = request.args.get('q', '').strip()
    status_f = request.args.get('status', '')
    cat_f = request.args.get('category', '')
    ser_f = request.args.get('series', '')

    sql = '''
        SELECT b.*, c.name AS category_name, s.name AS series_name,
               COALESCE(inv.stock_quantity, 0) AS stock,
               GROUP_CONCAT(a.name, ', ') AS authors
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN series s ON b.series_id = s.id
        LEFT JOIN inventory inv ON b.id = inv.book_id
        LEFT JOIN book_authors ba ON b.id = ba.book_id
        LEFT JOIN authors a ON ba.author_id = a.id
        WHERE 1=1
    '''
    params = []
    if q:
        sql += ' AND b.title LIKE ?'
        params.append(f'%{q}%')
    if status_f:
        sql += ' AND b.status = ?'
        params.append(status_f)
    if cat_f:
        sql += ' AND b.category_id = ?'
        params.append(cat_f)
    if ser_f:
        sql += ' AND b.series_id = ?'
        params.append(ser_f)
    sql += ' GROUP BY b.id ORDER BY b.title'

    books = db.execute(sql, params).fetchall()
    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    series = db.execute('SELECT * FROM series ORDER BY name').fetchall()
    db.close()
    return render_template('catalog.html', books=books,
        categories=categories, series=series,
        book_statuses=BOOK_STATUSES, q=q,
        status_f=status_f, cat_f=cat_f, ser_f=ser_f)


@app.route('/catalog/add', methods=['GET', 'POST'])
@login_required
def catalog_add():
    db = get_db()
    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    series = db.execute('SELECT * FROM series ORDER BY name').fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('שם הספר הוא שדה חובה', 'danger')
        elif db.execute('SELECT id FROM books WHERE title=?', (title,)).fetchone():
            flash('ספר עם שם זה כבר קיים', 'danger')
        else:
            cur = db.execute('''
                INSERT INTO books (title, isbn, description, cover_image_url,
                    publication_date, list_price, status, category_id, series_id, series_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                request.form.get('isbn', '').strip() or None,
                request.form.get('description', '').strip() or None,
                request.form.get('cover_image_url', '').strip() or None,
                request.form.get('publication_date', '').strip() or None,
                float(request.form.get('list_price') or 0) or None,
                request.form.get('status', 'טיוטה'),
                request.form.get('category_id') or None,
                request.form.get('series_id') or None,
                request.form.get('series_order') or None,
            ))
            book_id = cur.lastrowid
            # Create inventory record
            db.execute('INSERT OR IGNORE INTO inventory (book_id) VALUES (?)', (book_id,))
            # Auto-create production stages
            for i, stage in enumerate(PRODUCTION_STAGES_LIST):
                db.execute('''
                    INSERT INTO production_stages (book_id, stage, status)
                    VALUES (?, ?, 'ממתין')
                ''', (book_id, stage))
            db.commit()
            db.close()
            flash(f'הספר "{title}" נוסף בהצלחה', 'success')
            return redirect(url_for('catalog_detail', bid=book_id))

    db.close()
    return render_template('catalog_form.html',
        book=None, categories=categories, series=series,
        book_statuses=BOOK_STATUSES)


@app.route('/catalog/<int:bid>')
@login_required
def catalog_detail(bid):
    db = get_db()
    book = db.execute('''
        SELECT b.*, c.name AS category_name, s.name AS series_name,
               COALESCE(inv.stock_quantity, 0) AS stock,
               inv.reorder_threshold
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN series s ON b.series_id = s.id
        LEFT JOIN inventory inv ON b.id = inv.book_id
        WHERE b.id = ?
    ''', (bid,)).fetchone()
    if not book:
        db.close()
        flash('ספר לא נמצא', 'danger')
        return redirect(url_for('catalog'))

    book_authors = db.execute('''
        SELECT a.id, a.name, ba.role, ba.royalty_pct
        FROM book_authors ba JOIN authors a ON ba.author_id = a.id
        WHERE ba.book_id = ? ORDER BY a.name
    ''', (bid,)).fetchall()

    all_authors = db.execute('SELECT id, name FROM authors ORDER BY name').fetchall()

    stages = db.execute('''
        SELECT * FROM production_stages WHERE book_id = ?
        ORDER BY CASE stage
            WHEN 'כתב יד' THEN 1 WHEN 'עריכה' THEN 2 WHEN 'הגהה' THEN 3
            WHEN 'עימוד' THEN 4 WHEN 'עיצוב כריכה' THEN 5
            WHEN 'דפוס' THEN 6 WHEN 'הפצה' THEN 7 ELSE 8 END
    ''', (bid,)).fetchall()

    print_runs = db.execute('''
        SELECT * FROM print_runs WHERE book_id = ? ORDER BY run_date DESC
    ''', (bid,)).fetchall()

    financials = db.execute('''
        SELECT
            COALESCE(SUM(CASE WHEN type="הכנסה" THEN amount_accounting ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type="הוצאה" THEN amount_accounting ELSE 0 END), 0) AS expenses,
            COALESCE(SUM(amount_accounting), 0) AS net
        FROM transactions WHERE book = ?
    ''', (book['title'],)).fetchone()

    bundles = db.execute('''
        SELECT bun.name FROM bundles bun
        JOIN bundle_books bb ON bun.id = bb.bundle_id
        WHERE bb.book_id = ?
    ''', (bid,)).fetchall()

    db.close()
    return render_template('catalog_detail.html',
        book=book, book_authors=book_authors, all_authors=all_authors,
        stages=stages, print_runs=print_runs, financials=financials,
        bundles=bundles, author_roles=AUTHOR_ROLES,
        production_stages_list=PRODUCTION_STAGES_LIST,
        production_statuses=PRODUCTION_STATUSES)


@app.route('/catalog/<int:bid>/edit', methods=['GET', 'POST'])
@login_required
def catalog_edit(bid):
    db = get_db()
    book = db.execute('SELECT * FROM books WHERE id=?', (bid,)).fetchone()
    if not book:
        db.close()
        flash('ספר לא נמצא', 'danger')
        return redirect(url_for('catalog'))

    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    series = db.execute('SELECT * FROM series ORDER BY name').fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('שם הספר הוא שדה חובה', 'danger')
        else:
            existing = db.execute(
                'SELECT id FROM books WHERE title=? AND id!=?', (title, bid)
            ).fetchone()
            if existing:
                flash('ספר עם שם זה כבר קיים', 'danger')
            else:
                db.execute('''
                    UPDATE books SET title=?, isbn=?, description=?, cover_image_url=?,
                        publication_date=?, list_price=?, status=?,
                        category_id=?, series_id=?, series_order=?
                    WHERE id=?
                ''', (
                    title,
                    request.form.get('isbn', '').strip() or None,
                    request.form.get('description', '').strip() or None,
                    request.form.get('cover_image_url', '').strip() or None,
                    request.form.get('publication_date', '').strip() or None,
                    float(request.form.get('list_price') or 0) or None,
                    request.form.get('status', 'טיוטה'),
                    request.form.get('category_id') or None,
                    request.form.get('series_id') or None,
                    request.form.get('series_order') or None,
                    bid,
                ))
                db.commit()
                db.close()
                flash('הספר עודכן בהצלחה', 'success')
                return redirect(url_for('catalog_detail', bid=bid))

    db.close()
    return render_template('catalog_form.html',
        book=book, categories=categories, series=series,
        book_statuses=BOOK_STATUSES)


@app.route('/catalog/<int:bid>/delete', methods=['POST'])
@login_required
def catalog_delete(bid):
    db = get_db()
    book = db.execute('SELECT title FROM books WHERE id=?', (bid,)).fetchone()
    if book:
        db.execute('DELETE FROM books WHERE id=?', (bid,))
        db.commit()
        flash(f'הספר "{book["title"]}" נמחק', 'warning')
    db.close()
    return redirect(url_for('catalog'))


# ── Book Authors (from detail page) ──────────────────────────────────────────

@app.route('/catalog/<int:bid>/authors/add', methods=['POST'])
@login_required
def catalog_author_add(bid):
    author_id = request.form.get('author_id')
    role = request.form.get('role', 'מחבר')
    royalty = float(request.form.get('royalty_pct') or 0)
    db = get_db()
    try:
        db.execute('''
            INSERT OR REPLACE INTO book_authors (book_id, author_id, role, royalty_pct)
            VALUES (?, ?, ?, ?)
        ''', (bid, author_id, role, royalty))
        db.commit()
        flash('המחבר נוסף', 'success')
    except Exception as e:
        flash(f'שגיאה: {e}', 'danger')
    db.close()
    return redirect(url_for('catalog_detail', bid=bid) + '#tab-authors')


@app.route('/catalog/<int:bid>/authors/<int:aid>/remove', methods=['POST'])
@login_required
def catalog_author_remove(bid, aid):
    db = get_db()
    db.execute('DELETE FROM book_authors WHERE book_id=? AND author_id=?', (bid, aid))
    db.commit()
    db.close()
    flash('המחבר הוסר', 'warning')
    return redirect(url_for('catalog_detail', bid=bid) + '#tab-authors')


# ── Production Stages (from detail page) ─────────────────────────────────────

@app.route('/catalog/<int:bid>/stages/add', methods=['POST'])
@login_required
def stage_add(bid):
    db = get_db()
    db.execute('''
        INSERT INTO production_stages (book_id, stage, status, deadline, assigned_to, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        bid,
        request.form.get('stage', '').strip(),
        request.form.get('status', 'ממתין'),
        request.form.get('deadline', '').strip() or None,
        request.form.get('assigned_to', '').strip() or None,
        request.form.get('notes', '').strip() or None,
    ))
    db.commit()
    db.close()
    flash('שלב נוסף', 'success')
    return redirect(url_for('catalog_detail', bid=bid) + '#tab-production')


@app.route('/stages/<int:sid>/update', methods=['POST'])
@login_required
def stage_update(sid):
    db = get_db()
    stage = db.execute('SELECT book_id FROM production_stages WHERE id=?', (sid,)).fetchone()
    new_status = request.form.get('status', 'ממתין')
    completed_at = 'CURRENT_TIMESTAMP' if new_status == 'הושלם' else None
    if completed_at:
        db.execute('''
            UPDATE production_stages
            SET status=?, deadline=?, assigned_to=?, notes=?, completed_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            new_status,
            request.form.get('deadline', '').strip() or None,
            request.form.get('assigned_to', '').strip() or None,
            request.form.get('notes', '').strip() or None,
            sid,
        ))
    else:
        db.execute('''
            UPDATE production_stages
            SET status=?, deadline=?, assigned_to=?, notes=?, completed_at=NULL
            WHERE id=?
        ''', (
            new_status,
            request.form.get('deadline', '').strip() or None,
            request.form.get('assigned_to', '').strip() or None,
            request.form.get('notes', '').strip() or None,
            sid,
        ))
    db.commit()
    bid = stage['book_id'] if stage else 0
    db.close()
    flash('שלב עודכן', 'success')
    return redirect(url_for('catalog_detail', bid=bid) + '#tab-production')


@app.route('/stages/<int:sid>/delete', methods=['POST'])
@login_required
def stage_delete(sid):
    db = get_db()
    stage = db.execute('SELECT book_id FROM production_stages WHERE id=?', (sid,)).fetchone()
    bid = stage['book_id'] if stage else 0
    db.execute('DELETE FROM production_stages WHERE id=?', (sid,))
    db.commit()
    db.close()
    flash('שלב נמחק', 'warning')
    return redirect(url_for('catalog_detail', bid=bid) + '#tab-production')


# ── Authors ───────────────────────────────────────────────────────────────────

@app.route('/authors', methods=['GET', 'POST'])
@login_required
def authors():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('שם המחבר הוא שדה חובה', 'danger')
        else:
            db.execute('''
                INSERT INTO authors (name, bio, email, phone)
                VALUES (?, ?, ?, ?)
            ''', (
                name,
                request.form.get('bio', '').strip() or None,
                request.form.get('email', '').strip() or None,
                request.form.get('phone', '').strip() or None,
            ))
            db.commit()
            flash(f'המחבר "{name}" נוסף', 'success')

    authors_list = db.execute('''
        SELECT a.*, COUNT(ba.book_id) AS book_count
        FROM authors a
        LEFT JOIN book_authors ba ON a.id = ba.author_id
        GROUP BY a.id ORDER BY a.name
    ''').fetchall()
    db.close()
    return render_template('authors.html', authors=authors_list)


@app.route('/authors/<int:aid>/edit', methods=['GET', 'POST'])
@login_required
def author_edit(aid):
    db = get_db()
    author = db.execute('SELECT * FROM authors WHERE id=?', (aid,)).fetchone()
    if not author:
        db.close()
        flash('מחבר לא נמצא', 'danger')
        return redirect(url_for('authors'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('שם המחבר הוא שדה חובה', 'danger')
        else:
            db.execute('''
                UPDATE authors SET name=?, bio=?, email=?, phone=? WHERE id=?
            ''', (
                name,
                request.form.get('bio', '').strip() or None,
                request.form.get('email', '').strip() or None,
                request.form.get('phone', '').strip() or None,
                aid,
            ))
            db.commit()
            db.close()
            flash('המחבר עודכן', 'success')
            return redirect(url_for('authors'))

    db.close()
    return render_template('author_edit.html', author=author)


@app.route('/authors/<int:aid>/delete', methods=['POST'])
@login_required
def author_delete(aid):
    db = get_db()
    author = db.execute('SELECT name FROM authors WHERE id=?', (aid,)).fetchone()
    if author:
        db.execute('DELETE FROM authors WHERE id=?', (aid,))
        db.commit()
        flash(f'המחבר "{author["name"]}" נמחק', 'warning')
    db.close()
    return redirect(url_for('authors'))


# ── Categories & Series ───────────────────────────────────────────────────────

def _cats_and_series(db):
    cats = db.execute('''
        SELECT c.*, COUNT(b.id) AS book_count
        FROM categories c LEFT JOIN books b ON b.category_id = c.id
        GROUP BY c.id ORDER BY c.name
    ''').fetchall()
    series_list = db.execute('''
        SELECT s.*, COUNT(b.id) AS book_count
        FROM series s LEFT JOIN books b ON b.series_id = s.id
        GROUP BY s.id ORDER BY s.name
    ''').fetchall()
    return cats, series_list


@app.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip() or None
        if not name:
            flash('שם הקטגוריה חסר', 'danger')
        elif db.execute('SELECT id FROM categories WHERE name=?', (name,)).fetchone():
            flash('קטגוריה זו כבר קיימת', 'danger')
        else:
            db.execute('INSERT INTO categories (name, description) VALUES (?, ?)', (name, desc))
            db.commit()
            flash(f'קטגוריה "{name}" נוספה', 'success')

    cats, series_list = _cats_and_series(db)
    db.close()
    return render_template('categories.html', categories=cats, series=series_list)


@app.route('/categories/<int:cid>/delete', methods=['POST'])
@login_required
def category_delete(cid):
    db = get_db()
    cat = db.execute('SELECT name FROM categories WHERE id=?', (cid,)).fetchone()
    if cat:
        db.execute('DELETE FROM categories WHERE id=?', (cid,))
        db.commit()
        flash(f'קטגוריה "{cat["name"]}" נמחקה', 'warning')
    db.close()
    return redirect(url_for('categories'))


@app.route('/series', methods=['GET', 'POST'])
@login_required
def series():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip() or None
        if not name:
            flash('שם הסדרה חסר', 'danger')
        elif db.execute('SELECT id FROM series WHERE name=?', (name,)).fetchone():
            flash('סדרה זו כבר קיימת', 'danger')
        else:
            db.execute('INSERT INTO series (name, description) VALUES (?, ?)', (name, desc))
            db.commit()
            flash(f'סדרה "{name}" נוספה', 'success')

    cats, series_list = _cats_and_series(db)
    db.close()
    return render_template('categories.html', categories=cats, series=series_list)


@app.route('/series/<int:sid>/delete', methods=['POST'])
@login_required
def series_delete(sid):
    db = get_db()
    s = db.execute('SELECT name FROM series WHERE id=?', (sid,)).fetchone()
    if s:
        db.execute('DELETE FROM series WHERE id=?', (sid,))
        db.commit()
        flash(f'סדרה "{s["name"]}" נמחקה', 'warning')
    db.close()
    return redirect(url_for('series'))


# ── Bundles ───────────────────────────────────────────────────────────────────

@app.route('/bundles')
@login_required
def bundles():
    db = get_db()
    bundles_raw = db.execute('SELECT * FROM bundles ORDER BY name').fetchall()
    bundle_books_raw = db.execute('''
        SELECT bb.bundle_id, b.id, b.title, b.list_price
        FROM bundle_books bb JOIN books b ON bb.book_id = b.id
        ORDER BY b.title
    ''').fetchall()
    db.close()

    books_by_bundle = {}
    for bb in bundle_books_raw:
        books_by_bundle.setdefault(bb['bundle_id'], []).append(bb)

    bundles_list = []
    for b in bundles_raw:
        d = dict(b)
        d['books'] = books_by_bundle.get(b['id'], [])
        bundles_list.append(d)

    return render_template('bundles.html', bundles=bundles_list)


@app.route('/bundles/add', methods=['GET', 'POST'])
@login_required
def bundle_add():
    db = get_db()
    all_books = db.execute('SELECT id, title FROM books ORDER BY title').fetchall()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('שם החבילה חסר', 'danger')
        elif db.execute('SELECT id FROM bundles WHERE name=?', (name,)).fetchone():
            flash('חבילה עם שם זה כבר קיימת', 'danger')
        else:
            cur = db.execute('''
                INSERT INTO bundles (name, description, bundle_price, active)
                VALUES (?, ?, ?, ?)
            ''', (
                name,
                request.form.get('description', '').strip() or None,
                float(request.form.get('bundle_price') or 0) or None,
                1 if request.form.get('active') else 0,
            ))
            bid = cur.lastrowid
            for book_id in request.form.getlist('book_ids'):
                db.execute('INSERT OR IGNORE INTO bundle_books (bundle_id, book_id) VALUES (?, ?)',
                           (bid, book_id))
            db.commit()
            db.close()
            flash(f'חבילה "{name}" נוספה', 'success')
            return redirect(url_for('bundles'))

    db.close()
    return render_template('bundle_form.html', bundle=None, all_books=all_books, selected_ids=[])


@app.route('/bundles/<int:bid>/edit', methods=['GET', 'POST'])
@login_required
def bundle_edit(bid):
    db = get_db()
    bundle = db.execute('SELECT * FROM bundles WHERE id=?', (bid,)).fetchone()
    if not bundle:
        db.close()
        flash('חבילה לא נמצאה', 'danger')
        return redirect(url_for('bundles'))

    all_books = db.execute('SELECT id, title FROM books ORDER BY title').fetchall()
    selected_ids = [r['book_id'] for r in db.execute(
        'SELECT book_id FROM bundle_books WHERE bundle_id=?', (bid,)
    ).fetchall()]

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('שם החבילה חסר', 'danger')
        else:
            db.execute('''
                UPDATE bundles SET name=?, description=?, bundle_price=?, active=?
                WHERE id=?
            ''', (
                name,
                request.form.get('description', '').strip() or None,
                float(request.form.get('bundle_price') or 0) or None,
                1 if request.form.get('active') else 0,
                bid,
            ))
            db.execute('DELETE FROM bundle_books WHERE bundle_id=?', (bid,))
            for book_id in request.form.getlist('book_ids'):
                db.execute('INSERT OR IGNORE INTO bundle_books (bundle_id, book_id) VALUES (?, ?)',
                           (bid, book_id))
            db.commit()
            db.close()
            flash('החבילה עודכנה', 'success')
            return redirect(url_for('bundles'))

    db.close()
    return render_template('bundle_form.html', bundle=bundle,
        all_books=all_books, selected_ids=selected_ids)


@app.route('/bundles/<int:bid>/delete', methods=['POST'])
@login_required
def bundle_delete(bid):
    db = get_db()
    bundle = db.execute('SELECT name FROM bundles WHERE id=?', (bid,)).fetchone()
    if bundle:
        db.execute('DELETE FROM bundles WHERE id=?', (bid,))
        db.commit()
        flash(f'חבילה "{bundle["name"]}" נמחקה', 'warning')
    db.close()
    return redirect(url_for('bundles'))


# ── Inventory ─────────────────────────────────────────────────────────────────

@app.route('/inventory')
@login_required
def inventory():
    db = get_db()
    books = db.execute('''
        SELECT b.id, b.title, b.status,
               COALESCE(inv.stock_quantity, 0) AS stock,
               COALESCE(inv.reorder_threshold, 50) AS reorder_threshold
        FROM books b
        LEFT JOIN inventory inv ON b.id = inv.book_id
        ORDER BY b.title
    ''').fetchall()
    print_runs = db.execute('''
        SELECT pr.*, b.title AS book_title
        FROM print_runs pr JOIN books b ON pr.book_id = b.id
        ORDER BY pr.run_date DESC LIMIT 20
    ''').fetchall()
    db.close()

    total_stock = sum(b['stock'] for b in books)
    stats = {
        'total_books': len(books),
        'total_stock': total_stock,
        'low_stock': sum(1 for b in books if 0 < b['stock'] <= b['reorder_threshold']),
        'out_of_stock': sum(1 for b in books if b['stock'] == 0),
    }
    return render_template('inventory.html', books=books,
        print_runs=print_runs, stats=stats)


@app.route('/inventory/<int:bid>/update', methods=['POST'])
@login_required
def inventory_update(bid):
    qty = int(request.form.get('stock_quantity', 0))
    threshold = int(request.form.get('reorder_threshold', 50))
    db = get_db()
    db.execute('''
        INSERT INTO inventory (book_id, stock_quantity, reorder_threshold, last_updated)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(book_id) DO UPDATE SET
            stock_quantity=excluded.stock_quantity,
            reorder_threshold=excluded.reorder_threshold,
            last_updated=CURRENT_TIMESTAMP
    ''', (bid, qty, threshold))
    db.commit()
    db.close()
    flash('המלאי עודכן', 'success')
    return redirect(url_for('inventory'))


@app.route('/print-runs/add', methods=['POST'])
@login_required
def print_run_add():
    db = get_db()
    book_id = request.form.get('book_id')
    quantity = int(request.form.get('quantity', 0))
    run_date = request.form.get('run_date', '').strip()
    if not book_id or not quantity or not run_date:
        flash('יש למלא ספר, כמות ותאריך', 'danger')
    else:
        db.execute('''
            INSERT INTO print_runs (book_id, run_date, quantity, cost_per_unit, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            book_id, run_date, quantity,
            float(request.form.get('cost_per_unit') or 0) or None,
            request.form.get('notes', '').strip() or None,
        ))
        # Update inventory stock
        db.execute('''
            INSERT INTO inventory (book_id, stock_quantity, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(book_id) DO UPDATE SET
                stock_quantity = stock_quantity + ?,
                last_updated = CURRENT_TIMESTAMP
        ''', (book_id, quantity, quantity))
        db.commit()
        flash('הדפסה נוספה והמלאי עודכן', 'success')
    db.close()
    return redirect(url_for('inventory'))


@app.route('/print-runs/<int:rid>/delete', methods=['POST'])
@login_required
def print_run_delete(rid):
    db = get_db()
    pr = db.execute('SELECT * FROM print_runs WHERE id=?', (rid,)).fetchone()
    if pr:
        db.execute('DELETE FROM print_runs WHERE id=?', (rid,))
        db.commit()
        flash('רשומת הדפסה נמחקה', 'warning')
    db.close()
    return redirect(url_for('inventory'))


# ── Production Overview ───────────────────────────────────────────────────────

@app.route('/production')
@login_required
def production():
    db = get_db()
    books = db.execute('SELECT id, title, status FROM books ORDER BY title').fetchall()
    stages_raw = db.execute('SELECT * FROM production_stages').fetchall()
    db.close()

    # Build {book_id: {stage_name: stage_row}}
    pivot = {}
    for s in stages_raw:
        pivot.setdefault(s['book_id'], {})[s['stage']] = s

    stage_names = PRODUCTION_STAGES_LIST

    grid = [
        {'book_id': b['id'], 'title': b['title'], 'stages': pivot.get(b['id'], {})}
        for b in books
    ]

    stage_summary = []
    for stage in stage_names:
        counts = {'stage': stage, 'done': 0, 'in_progress': 0, 'pending': 0, 'delayed': 0}
        for s in stages_raw:
            if s['stage'] == stage:
                if s['status'] == 'הושלם':
                    counts['done'] += 1
                elif s['status'] == 'בתהליך':
                    counts['in_progress'] += 1
                elif s['status'] == 'עיכוב':
                    counts['delayed'] += 1
                else:
                    counts['pending'] += 1
        stage_summary.append(counts)

    return render_template('production.html',
        grid=grid, stage_names=stage_names, stage_summary=stage_summary)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/books')
@login_required
def api_books():
    return jsonify(get_books_list())


@app.route('/api/items')
@login_required
def api_items():
    return jsonify(ITEMS)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=True, port=port)
