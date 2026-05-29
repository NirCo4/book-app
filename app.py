from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'books-store-2026'

DB_PATH = os.path.join(os.path.dirname(__file__), 'books.db')

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


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def status_filter_sql(status_filter):
    """Return WHERE clause fragment for status filter."""
    if status_filter == 'תכנון':
        return "status = 'תכנון'"
    elif status_filter == 'בפועל':
        return "status != 'תכנון'"
    return '1=1'


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/')
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

    # Cumulative net and trough
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
        if not month:
            errors.append('יש לבחור חודש')
        if not book:
            errors.append('יש לבחור ספר')
        if not status:
            errors.append('יש לבחור סטטוס')
        if not ttype:
            errors.append('יש לבחור סוג תנועה')
        if not item:
            errors.append('יש לבחור פריט')
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
                INSERT INTO transactions (month, book, status, type, item, amount_positive, amount_accounting, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (month, book, status, ttype, item, amount, accounting, notes or None))
            db.commit()
            db.close()
            flash('הרשומה נשמרה בהצלחה', 'success')
            return redirect(url_for('entry'))

    db = get_db()
    recent = db.execute('''
        SELECT * FROM transactions ORDER BY id DESC LIMIT 20
    ''').fetchall()
    db.close()
    return render_template('entry.html',
        books=BOOKS, months=MONTHS, statuses=STATUSES, types=TYPES,
        items=ITEMS, recent=recent, month_labels=MONTH_LABELS)


@app.route('/entry/<int:tid>/edit', methods=['GET', 'POST'])
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
                books=BOOKS, months=MONTHS, statuses=STATUSES,
                types=TYPES, items=ITEMS, month_labels=MONTH_LABELS)

        accounting = amount if ttype == 'הכנסה' else -amount
        db.execute('''
            UPDATE transactions
            SET month=?, book=?, status=?, type=?, item=?, amount_positive=?, amount_accounting=?, notes=?
            WHERE id=?
        ''', (month, book, status, ttype, item, amount, accounting, notes or None, tid))
        db.commit()
        db.close()
        flash('הרשומה עודכנה בהצלחה', 'success')
        return redirect(url_for('entry'))

    db.close()
    return render_template('entry_edit.html', row=row,
        books=BOOKS, months=MONTHS, statuses=STATUSES,
        types=TYPES, items=ITEMS, month_labels=MONTH_LABELS)


@app.route('/entry/<int:tid>/delete', methods=['POST'])
def delete_entry(tid):
    db = get_db()
    db.execute('DELETE FROM transactions WHERE id=?', (tid,))
    db.commit()
    db.close()
    flash('הרשומה נמחקה', 'warning')
    return redirect(url_for('entry'))


# ── Monthly Summary ───────────────────────────────────────────────────────────

@app.route('/monthly')
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

    # Cashflow view (status=תזרים only)
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
        GROUP BY book
        ORDER BY CASE book
            {' '.join(f"WHEN '{b}' THEN {i}" for i, b in enumerate(BOOKS))}
            ELSE 999 END
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
    db.close()

    # Get distinct months that have data
    data_months = sorted({r['month'] for r in rows})
    # Use all configured months but only show ones with data (or all months)
    use_months = [m for m in MONTHS if m in data_months] or data_months

    # Build pivot dict
    pivot = {}
    for r in rows:
        pivot.setdefault(r['book'], {})[r['month']] = r['value']

    matrix_rows = []
    for book in BOOKS:
        if book not in pivot and not any(r['book'] == book for r in rows):
            # Skip books with zero data unless explicitly listed
            continue
        month_vals = [pivot.get(book, {}).get(m, 0) for m in use_months]
        total = sum(month_vals)
        matrix_rows.append({'book': book, 'vals': month_vals, 'total': total})

    col_totals = [sum(r['vals'][i] for r in matrix_rows) for i in range(len(use_months))]
    grand_total = sum(col_totals)

    return render_template('matrix.html',
        months=use_months, month_labels=MONTH_LABELS,
        rows=matrix_rows, col_totals=col_totals, grand_total=grand_total,
        status=status, view=view)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/books')
def api_books():
    return jsonify(BOOKS)


@app.route('/api/items')
def api_items():
    return jsonify(ITEMS)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=True, port=port)
