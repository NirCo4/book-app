"""Initialize DB and import existing Excel data."""
import sqlite3
import os
import pandas as pd
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'books.db')
EXCEL_PATH = os.path.join(os.path.dirname(__file__), 'Books_Details.xlsx')

DEFAULT_BOOKS = [
    'סופרות בטרם עת', 'גן עדן לחתולים', 'קמצנים, חמדנים, עסקנים',
    'שני סיפורים נודדים', 'מקאריו', 'דרכים חלופיות', 'עץ הקיפודים',
    'משחק הגורלות', 'גרוסמן', 'ביאליק', 'דוסטויבסקי', 'בלזק',
    'כללי (משותף לסדרה)'
]


def init_db(conn):
    conn.execute('PRAGMA foreign_keys = ON')

    # ── Transactions (recreated fresh from Excel) ──────────────────────────────
    conn.execute('DROP TABLE IF EXISTS transactions')
    conn.execute('''
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            book TEXT NOT NULL,
            status TEXT NOT NULL,
            type TEXT NOT NULL,
            item TEXT NOT NULL,
            amount_positive REAL NOT NULL,
            amount_accounting REAL NOT NULL,
            notes TEXT,
            entered_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Users (preserved across restarts) ─────────────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')
    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                     ('admin', generate_password_hash('admin')))
        print('Default user created: admin / admin')

    # ── Catalog tables (preserved across restarts) ─────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bio TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE,
            isbn TEXT,
            description TEXT,
            cover_image_url TEXT,
            publication_date TEXT,
            list_price REAL,
            status TEXT NOT NULL DEFAULT 'published',
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            series_id INTEGER REFERENCES series(id) ON DELETE SET NULL,
            series_order INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS book_authors (
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
            role TEXT DEFAULT 'מחבר',
            royalty_pct REAL DEFAULT 0,
            PRIMARY KEY (book_id, author_id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            bundle_price REAL,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS bundle_books (
            bundle_id INTEGER NOT NULL REFERENCES bundles(id) ON DELETE CASCADE,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            PRIMARY KEY (bundle_id, book_id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS print_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            run_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            cost_per_unit REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
            stock_quantity INTEGER DEFAULT 0,
            reorder_threshold INTEGER DEFAULT 50,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS production_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            stage TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ממתין',
            deadline TEXT,
            assigned_to TEXT,
            notes TEXT,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Seed default books (INSERT OR IGNORE preserves existing catalog data)
    for title in DEFAULT_BOOKS:
        conn.execute('INSERT OR IGNORE INTO books (title, status) VALUES (?, ?)',
                     (title, 'published'))
        conn.execute('''
            INSERT OR IGNORE INTO inventory (book_id, stock_quantity)
            SELECT id, 0 FROM books WHERE title = ?
        ''', (title,))

    conn.commit()


def import_excel(conn):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        df = pd.read_excel(EXCEL_PATH, sheet_name='Data להזנה', header=None)

    data = df.iloc[2:].copy()
    data.columns = ['id', 'month', 'book', 'status', 'type', 'item',
                    'amount_positive', 'amount_accounting', 'notes']

    inserted = 0
    for _, row in data.iterrows():
        try:
            if pd.isna(row['month']) or pd.isna(row['book']):
                continue
            month = str(row['month'])[:7]
            book = str(row['book']).strip()
            status = str(row['status']).strip()
            ttype = str(row['type']).strip()
            item = str(row['item']).strip()
            amount_pos = float(row['amount_positive']) if pd.notna(row['amount_positive']) else 0.0
            amount_acc = float(row['amount_accounting']) if pd.notna(row['amount_accounting']) else 0.0
            notes = None if pd.isna(row['notes']) else str(row['notes']).strip()

            conn.execute('''
                INSERT INTO transactions
                    (month, book, status, type, item, amount_positive, amount_accounting, notes, entered_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (month, book, status, ttype, item, amount_pos, amount_acc, notes, 'Excel import'))
            inserted += 1
        except Exception as e:
            print(f'  Skip row: {e}')

    conn.commit()
    print(f'Imported {inserted} transactions.')


if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    print('Creating database...')
    init_db(conn)
    if os.path.exists(EXCEL_PATH):
        print('Importing from Excel...')
        import_excel(conn)
    else:
        print('Excel not found, starting with empty DB.')
    conn.close()
    print(f'Done. Database saved to {DB_PATH}')
