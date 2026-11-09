"""
The Leaky Invoice - A CTF Challenge Demonstrating Broken Object-Level Authorization

Beginner difficulty: Participants log in as a normal user, follow an in-application
reference to a record that is not theirs, and read data the server never checked
they were allowed to see.

The vulnerability is a missing authorization check on a single route. The invoice
identifiers are ordinary sequential database IDs on purpose, so the lesson is that
predictable IDs are not the root cause - missing access control is.
"""

import sqlite3
import os
import shutil
import uuid
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Validate required environment variables
if not os.environ.get('LEAKY_INVOICE_SECRET_KEY'):
    raise RuntimeError('LEAKY_INVOICE_SECRET_KEY environment variable is required')
if not os.environ.get('LEAKY_INVOICE_FLAG'):
    logger.warning('LEAKY_INVOICE_FLAG not set - will attempt to read from .flag file')

app.secret_key = os.environ.get('LEAKY_INVOICE_SECRET_KEY')
app.config['DATABASE'] = os.environ.get(
    'LEAKY_INVOICE_DATABASE',
    os.path.join(app.root_path, 'leaky_invoices.db'),
)

# Security configurations
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Security headers (Talisman)
# Note: CSP is relaxed for CTF simplicity, but headers are present
csp = {
    'default-src': "'self'",
    'style-src': ["'self'", "'unsafe-inline'"],
    'script-src': ["'self'", "'unsafe-inline'"],
}

# Only enforce HTTPS in production
force_https = os.environ.get('FLASK_ENV') == 'production'
Talisman(
    app,
    force_https=force_https,
    strict_transport_security=True,
    content_security_policy=csp,
    content_security_policy_nonce_in=['script-src']
)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)

# Flag configuration is local-only. The value is supplied by the operator through
# the LEAKY_INVOICE_FLAG environment variable or a local flag file. It is never
# committed to source control, rendered into a template, or shown on a page a
# participant reaches before exploitation.
FLAG_ENV_VAR = 'LEAKY_INVOICE_FLAG'
FLAG_FILENAME = '.flag'


class FlagConfigurationError(RuntimeError):
    """Raised when no usable flag value has been configured."""


def _flag_from_file():
    """Read the flag from the local, gitignored flag file if one exists."""
    path = os.path.join(app.root_path, FLAG_FILENAME)
    try:
        with open(path, encoding='utf-8') as handle:
            return handle.read().strip()
    except OSError:
        return None


def get_flag():
    """Return the configured CTF flag.

    Resolution order:
      1. the LEAKY_INVOICE_FLAG environment variable
      2. the local .flag file (gitignored)

    Raises FlagConfigurationError when neither provides a usable value, so the
    application refuses to start rather than seeding an empty or guessable flag.
    """
    value = (os.environ.get(FLAG_ENV_VAR) or '').strip() or _flag_from_file() or ''
    if not value:
        raise FlagConfigurationError(
            'No CTF flag configured. Set the '
            f'{FLAG_ENV_VAR} environment variable, or create a "{FLAG_FILENAME}" '
            'file next to app.py containing the flag. See the README setup steps. '
            'The flag is intentionally not stored in source control.'
        )
    return value


def backup_database():
    """Copy the database file aside before a structural migration runs.

    The backup is written alongside the database being protected, so a temporary
    or relocated database never writes into the application directory. Only
    called when a migration is about to modify an existing schema.
    """
    db_path = app.config['DATABASE']
    if not os.path.exists(db_path):
        return None
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    base = os.path.splitext(os.path.basename(db_path))[0]
    destination = os.path.join(backup_dir, f'{base}.{stamp}.pre-migration.db')
    shutil.copy2(db_path, destination)
    return destination


def _table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _assign_public_ids(cursor):
    """Ensure every invoice carries an opaque public identifier.

    Values are derived with uuid5 from the invoice number, so they are stable
    across restarts. Existing identifiers are never rewritten; only rows that
    are still NULL are filled in.
    """
    rows = cursor.execute(
        'SELECT id, invoice_number FROM invoices WHERE public_id IS NULL'
    ).fetchall()
    for row in rows:
        public_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, row['invoice_number']))
        cursor.execute(
            'UPDATE invoices SET public_id = ? WHERE id = ?', (public_id, row['id'])
        )


def _assign_legacy_refs(cursor):
    """Ensure every invoice carries an opaque legacy reference.

    Values are derived with uuid5 from the invoice number using a different
    namespace than public_id, so they are stable across restarts and distinct
    from the public identifiers. Existing identifiers are never rewritten;
    only rows that are still NULL are filled in.
    """
    rows = cursor.execute(
        'SELECT id, invoice_number FROM invoices WHERE legacy_ref IS NULL'
    ).fetchall()
    for row in rows:
        legacy_ref = str(uuid.uuid5(uuid.NAMESPACE_URL, row['invoice_number']))
        cursor.execute(
            'UPDATE invoices SET legacy_ref = ? WHERE id = ?', (legacy_ref, row['id'])
        )


def migrate_schema(cursor):
    """Apply additive, repeatable schema migrations.

    Every step checks the current schema first, so running this repeatedly is a
    no-op once the database is up to date. Existing rows are never deleted or
    renumbered.
    """
    if not _table_exists(cursor, 'notifications'):
        cursor.execute('''
            CREATE TABLE notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                reference_label TEXT NOT NULL,
                reference_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')

    # Older databases stored an opaque identifier in invoices.public_id. Newer
    # installs never had the column, so add it and populate any missing values.
    if _table_exists(cursor, 'invoices'):
        if not _column_exists(cursor, 'invoices', 'public_id'):
            cursor.execute('ALTER TABLE invoices ADD COLUMN public_id TEXT')
        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_public_id ON invoices(public_id)'
        )

    # Legacy reference identifiers added for the migration-era viewer.
    if _table_exists(cursor, 'invoices') and not _column_exists(cursor, 'invoices', 'legacy_ref'):
        cursor.execute('ALTER TABLE invoices ADD COLUMN legacy_ref TEXT')

    # Notifications gained a destination link so a notice can point at a section
    # of the application without naming a specific record.
    if _table_exists(cursor, 'notifications') and not _column_exists(cursor, 'notifications', 'link_path'):
        cursor.execute('ALTER TABLE notifications ADD COLUMN link_path TEXT')

    # Retire the earlier workspace notice. It named a specific historical record
    # and linked straight to it, which is not how this workspace communicates.
    cursor.execute(
        'DELETE FROM notifications WHERE title = ?',
        ('Shared workspace: Q1 archive consolidation',),
    )


UNSAFE_NOTICE_TITLE = 'Shared workspace: Q1 archive consolidation'
NOTICE_TITLE = 'System Notice: legacy invoice viewer (pre-2024 format)'
LEGACY_BASE_PATH = '/legacy/invoice/'

# One message for every unsuccessful lookup. Unknown reference and
# not-your-record must never be distinguishable from the outside.
INVOICE_NOT_FOUND_MESSAGE = 'Invoice not found.'


def _seed_notification(cursor):
    """Seed the single workspace notice describing the legacy invoice viewer.

    The copy is narrative only. It names no record, carries no identifier, and
    links to the viewer base path rather than to any particular invoice.
    """
    cursor.execute(
        'SELECT id FROM notifications WHERE title = ?', (NOTICE_TITLE,)
    )
    if cursor.fetchone() is not None:
        return

    cursor.execute('''
        INSERT INTO notifications (title, body, reference_label, reference_id, created_at, link_path)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        NOTICE_TITLE,
        'System Notice: The legacy invoice viewer (pre-2024 format) remains '
        'available for historical records during the ongoing migration. Records '
        'from that era are addressed by their original legacy reference numbers '
        'rather than the current numbering.',
        'Legacy invoice viewer',
        0,
        '2024-03-04',
        LEGACY_BASE_PATH,
    ))


def _seed_invoices(cursor, alice_id, bob_id, flag):
    """Insert the demo invoices if they are not present yet.

    Uses INSERT OR IGNORE on invoice_number, so existing invoices keep their
    original row ids, contents and ownership.
    """
    cursor.execute('''
        INSERT OR IGNORE INTO invoices (user_id, invoice_number, amount, description, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (alice_id, 'INV-2024-001', 1250.00, 'Web Development Services - Phase 1', '2024-01-15'))
    cursor.execute('''
        INSERT OR IGNORE INTO invoices (user_id, invoice_number, amount, description, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (alice_id, 'INV-2024-002', 750.00, 'Security Audit Consulting', '2024-02-01'))
    cursor.execute('''
        INSERT OR IGNORE INTO invoices (user_id, invoice_number, amount, description, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (alice_id, 'INV-2024-003', 300.00, 'Additional Consulting Services', '2024-03-01'))
    cursor.execute('''
        INSERT OR IGNORE INTO invoices (user_id, invoice_number, amount, description, created_at, is_private, legacy_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (bob_id, 'INV-2024-B1', 500.00, 'Server Maintenance - January', '2024-01-20', 0, None))
    cursor.execute('''
        INSERT OR IGNORE INTO invoices (user_id, invoice_number, amount, description, created_at, is_private, legacy_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (bob_id, 'INV-2024-B2', 1337.00, flag, '2024-02-15', 1, None))


def init_db():
    """Create the schema if needed, apply migrations, and seed demo data."""
    # Resolve the flag before touching the database, so a misconfigured install
    # fails immediately instead of creating rows with an unusable value.
    flag = get_flag()

    os.makedirs(os.path.dirname(os.path.abspath(app.config['DATABASE'])), exist_ok=True)
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_number TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_private BOOLEAN DEFAULT 0,
            public_id TEXT UNIQUE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Take a one-time backup before the first structural change on a pre-existing
    # database, so the original file is recoverable.
    needs_backup = _table_exists(cursor, 'users') and not _table_exists(cursor, 'notifications')
    if needs_backup:
        backup_database()
    migrate_schema(cursor)

    # Demo accounts. Alice's credentials are published in the README; Bob's are
    # not shared with participants. Passwords are hashed for security.
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES ('alice', ?)",
        (generate_password_hash('password123'),),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES ('bob', ?)",
        (generate_password_hash('BobVault!7392'),),
    )

    # Idempotent: only rewrites Bob's row while it still holds the old default.
    cursor.execute(
        "UPDATE users SET password = 'BobVault!7392' WHERE username = 'bob' AND password = 'password123'"
    )

    cursor.execute("SELECT id FROM users WHERE username = 'alice'")
    alice_id = cursor.fetchone()['id']
    cursor.execute("SELECT id FROM users WHERE username = 'bob'")
    bob_id = cursor.fetchone()['id']

    _seed_invoices(cursor, alice_id, bob_id, flag)

    # Every invoice needs an opaque identifier for the current viewer route.
    _assign_public_ids(cursor)

    # Every invoice needs an opaque legacy reference for the legacy viewer.
    _assign_legacy_refs(cursor)

    _seed_notification(cursor)

    db.commit()
    db.close()


def get_db():
    """Get database connection for the current request."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close database connection at end of request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def verify_password(username, password):
    """Verify user credentials using parameterized hash comparison."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    if row and check_password_hash(row['password'], password):
        return {'id': row['id'], 'username': username}
    return None


def get_user_invoices(user_id):
    """Get all invoices owned by a specific user."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM invoices WHERE user_id = ? ORDER BY id DESC', (user_id,))
    return cursor.fetchall()


def get_owned_invoice_by_public_id(user_id, public_id):
    """Fetch an invoice by its opaque identifier, scoped to its owner.

    Returns nothing when the identifier is unknown *or* when the record belongs
    to somebody else, so callers cannot tell the two cases apart.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT * FROM invoices WHERE public_id = ? AND user_id = ?', (public_id, user_id)
    )
    return cursor.fetchone()


def get_owned_invoice(user_id, invoice_id):
    """Fetch an invoice by sequential id, scoped to its owner."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM invoices WHERE id = ? AND user_id = ?', (invoice_id, user_id))
    return cursor.fetchone()


def get_invoice_by_legacy_id(legacy_ref):
    """Fetch an invoice by its opaque legacy reference.

    Deliberately unscoped. This backs the legacy viewer, which predates the
    ownership checks used by the current route. Returns nothing when the
    reference is unknown.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM invoices WHERE legacy_ref = ?', (legacy_ref,))
    return cursor.fetchone()


def get_company_directory():
    """List account holders by name only, for the legacy viewer's context panel."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT username FROM users ORDER BY id ASC')
    return [row['username'] for row in cursor.fetchall()]


def legacy_reference(invoice):
    """Return the opaque legacy reference from an invoice record."""
    return invoice['legacy_ref']


def get_notifications():
    """Get the workspace notifications shown to every signed-in user."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM notifications ORDER BY id ASC')
    return cursor.fetchall()


@app.route('/')
def index():
    """Home page - redirect to dashboard or login depending on session state."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Login page with rate limiting to prevent brute force attacks."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Input validation
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')
        
        if len(username) > 100 or len(password) > 100:
            flash('Invalid credentials.', 'error')
            return render_template('login.html')
        
        user = verify_password(username, password)

        if user:
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            logger.info(f"User logged in: {username}")
            return redirect(url_for('dashboard'))
        else:
            logger.warning(f"Failed login attempt for: {username}")
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session."""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"User logged out: {username}")
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    """Dashboard showing only the current user's own invoices."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    invoices = get_user_invoices(session['user_id'])
    return render_template('dashboard.html', invoices=invoices, username=session['username'])


@app.route('/legacy-tools')
@app.route('/legacy-tools/')
def legacy_tools():
    """Legacy tools archive portal - discoverable via robots.txt.

    Contains historical migration information, reference conventions,
    and subtle clues about the ongoing system migration. Not linked from
    any application page, only discoverable through robots.txt.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template(
        'legacy_tools.html',
        username=session['username'],
    )


@app.route('/notifications')
def notifications():
    """Workspace notifications shared with every signed-in user."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    items = get_notifications()
    return render_template('notifications.html', notifications=items, username=session['username'])


@app.route('/invoices/<public_id>')
def invoice_detail(public_id):
    """Current invoice viewer, addressed by opaque public identifier.

    Requires an authenticated session and returns only invoices owned by the
    signed-in user. An identifier belonging to another account is treated the
    same as one that does not exist.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    invoice = get_owned_invoice_by_public_id(session['user_id'], public_id)

    if not invoice:
        flash(INVOICE_NOT_FOUND_MESSAGE, 'error')
        return redirect(url_for('dashboard'))

    return render_template(
        'invoice.html',
        invoice=invoice,
        username=session['username'],
        legacy_reference=legacy_reference(invoice),
    )


@app.route('/legacy/invoice/')
def legacy_viewer_index():
    """Landing page for the pre-2024 legacy invoice viewer."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template(
        'legacy_index.html',
        username=session['username'],
        colleagues=get_company_directory(),
    )


@app.route('/legacy/invoice/<legacy_ref>')
def legacy_invoice_detail(legacy_ref):
    """Pre-2024 legacy invoice viewer - this is the intentionally broken route.

    It authenticates the visitor and then loads whatever record matches the
    legacy reference in the URL. It never compares the record owner against the
    signed-in user, so any signed-in user can read any invoice by asking for a
    different legacy reference number.

    Every other data access in this application is scoped to the current user.

    Unknown references and records owned by other accounts return an identical
    response, so this route does not confirm whether a reference exists.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    invoice = get_invoice_by_legacy_id(legacy_ref)

    if not invoice:
        flash(INVOICE_NOT_FOUND_MESSAGE, 'error')
        return redirect(url_for('dashboard'))

    return render_template(
        'legacy_invoice.html',
        invoice=invoice,
        username=session['username'],
        legacy_reference=legacy_reference(invoice),
        colleagues=get_company_directory(),
    )


@app.route('/robots.txt')
def robots_txt():
    """Robots.txt - publicly discoverable hints about application structure."""
    lines = [
        'User-agent: *',
        'Disallow: /legacy-tools/',
        'Allow: /',
        'Sitemap: none',
    ]
    return '\n'.join(lines), 200, {'Content-Type': 'text/plain'}


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    try:
        # Check database connectivity
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'database connection failed'
        }), 503


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    if 'user_id' in session:
        return render_template('error.html', 
                             error_code=404,
                             error_message='Page not found',
                             username=session.get('username')), 404
    return render_template('error.html', 
                         error_code=404,
                         error_message='Page not found'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    db = getattr(g, '_database', None)
    if db is not None:
        db.rollback()
    
    if 'user_id' in session:
        return render_template('error.html',
                             error_code=500,
                             error_message='Internal server error',
                             username=session.get('username')), 500
    return render_template('error.html',
                         error_code=500,
                         error_message='Internal server error'), 500


@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit errors."""
    logger.warning(f"Rate limit exceeded: {get_remote_address()}")
    return render_template('error.html',
                         error_code=429,
                         error_message='Too many requests. Please try again later.'), 429


if __name__ == '__main__':
    try:
        init_db()
    except FlagConfigurationError as exc:
        raise SystemExit(f"\nConfiguration error: {exc}\n")

    print("\n" + "=" * 60)
    print("  THE LEAKY INVOICE - CTF CHALLENGE")
    print("=" * 60)
    print("\n  Server starting on http://127.0.0.1:5001")
    print("\n  Demo account for participants:")
    print("    - alice / password123")
    print("\n  Task: this workspace holds two invoice viewers. Work out which of")
    print("  them keeps its records properly separated, and which one does not.")
    print("\n" + "=" * 60 + "\n")
    
    # Development server configuration
    logger.info("Starting development server - DO NOT USE IN PRODUCTION")
    app.run(host='127.0.0.1', port=5001, debug=False)