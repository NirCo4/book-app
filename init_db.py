"""Initialize DB and import existing Excel data."""
import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), 'books.db')
EXCEL_PATH = os.path.join(os.path.dirname(__file__), 'Books_Details.xlsx')


def init_db(conn):
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()


def import_excel(conn):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        df = pd.read_excel(EXCEL_PATH, sheet_name='Data להזנה', header=None)

    # Row 1 is header, data starts at row 2
    data = df.iloc[2:].copy()
    data.columns = ['id', 'month', 'book', 'status', 'type', 'item',
                    'amount_positive', 'amount_accounting', 'notes']

    inserted = 0
    for _, row in data.iterrows():
        try:
            if pd.isna(row['month']) or pd.isna(row['book']):
                continue
            month = str(row['month'])[:7]  # YYYY-MM
            book = str(row['book']).strip()
            status = str(row['status']).strip()
            ttype = str(row['type']).strip()
            item = str(row['item']).strip()
            amount_pos = float(row['amount_positive']) if pd.notna(row['amount_positive']) else 0.0
            amount_acc = float(row['amount_accounting']) if pd.notna(row['amount_accounting']) else 0.0
            notes = None if pd.isna(row['notes']) else str(row['notes']).strip()

            conn.execute('''
                INSERT INTO transactions (month, book, status, type, item, amount_positive, amount_accounting, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (month, book, status, ttype, item, amount_pos, amount_acc, notes))
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
