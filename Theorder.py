from flask import Flask, request, session, redirect, url_for, flash, render_template_string, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "theorders_secret_key_2025_change_me"
DATABASE = "theorders.db"

# ==================== DATABASE ====================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            cccd TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            last_active TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            created_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            delete_reason TEXT,
            FOREIGN KEY (seller_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    db.commit()

    # Tạo admin mặc định nếu chưa có
    cur = db.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        hashed = generate_password_hash("thanhtuan9988")
        db.execute("""
            INSERT INTO users (username, password, full_name, cccd, address, phone, is_admin, last_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, ("admin", hashed, "Quản Trị Viên", "000000000000", "Admin Address", "0000000000",
              datetime.now().isoformat(), datetime.now().isoformat()))
        db.commit()

# ==================== HELPERS ====================
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Bạn cần đăng nhập trước!", "warning")
            return redirect(url_for("login"))
        user = get_current_user()
        if user and user["is_banned"]:
            session.clear()
            flash("Tài khoản của bạn đã bị cấm!", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = get_current_user()
        if not user or not user["is_admin"]:
            flash("Bạn không có quyền truy cập!", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

def update_last_active(user_id):
    db = get_db()
    db.execute("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), user_id))
    db.commit()

def add_notification(user_id, message):
    db = get_db()
    db.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
               (user_id, message, datetime.now().isoformat()))
    db.commit()

# ==================== BASE TEMPLATE ====================
BASE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - TheOrders</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f0f2f5; color: #1a1a1a; }
        .navbar { background: #1e3a5f; color: white; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
        .navbar a { color: white; text-decoration: none; margin-left: 18px; font-weight: 500; }
        .navbar a:hover { opacity: 0.85; }
        .logo { height: 42px; border-radius: 6px; }
        .brand { font-size: 1.4rem; font-weight: 700; display: flex; align-items: center; gap: 12px; }
        .container { max-width: 1100px; margin: 30px auto; padding: 0 16px; }
        .card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
        .btn { display: inline-block; padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; text-decoration: none; transition: 0.2s; }
        .btn-primary { background: #2563eb; color: white; }
        .btn-primary:hover { background: #1d4ed8; }
        .btn-danger { background: #dc2626; color: white; }
        .btn-danger:hover { background: #b91c1c; }
        .btn-success { background: #16a34a; color: white; }
        .btn-warning { background: #d97706; color: white; }
        .btn-secondary { background: #64748b; color: white; }
        input, textarea, select { width: 100%; padding: 11px 14px; border: 1px solid #d1d5db; border-radius: 8px; margin-bottom: 14px; font-size: 15px; }
        label { font-weight: 600; display: block; margin-bottom: 6px; }
        .flash { padding: 14px 18px; border-radius: 8px; margin-bottom: 18px; font-weight: 500; }
        .flash.success { background: #dcfce7; color: #166534; }
        .flash.danger { background: #fee2e2; color: #991b1b; }
        .flash.warning { background: #fef3c7; color: #92400e; }
        .flash.info { background: #dbeafe; color: #1e40af; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f8fafc; font-weight: 600; }
        .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; }
        .product-card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.07); transition: 0.2s; }
        .product-card:hover { transform: translateY(-4px); box-shadow: 0 8px 20px rgba(0,0,0,0.12); }
        .product-body { padding: 16px; }
        .price { color: #dc2626; font-size: 1.25rem; font-weight: 700; }
        .chat-box { height: 420px; overflow-y: auto; background: #f8fafc; border-radius: 10px; padding: 16px; margin-bottom: 16px; border: 1px solid #e2e8f0; }
        .msg { margin-bottom: 12px; padding: 10px 14px; background: white; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
        .msg .author { font-weight: 700; color: #1e40af; }
        .msg .time { font-size: 0.8rem; color: #64748b; }
        .notif { background: #fefce8; border-left: 4px solid #eab308; padding: 12px 16px; margin-bottom: 10px; border-radius: 0 8px 8px 0; }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="brand">
            <img src="/static/logo.jpg" alt="Logo" class="logo" onerror="this.style.display='none'">
            TheOrders
        </div>
        <div>
            {% if user %}
                <a href="{{ url_for('index') }}">Trang chủ</a>
                <a href="{{ url_for('sell') }}">Đăng bán</a>
                <a href="{{ url_for('chat') }}">Chat chung</a>
                {% if user.is_admin %}
                    <a href="{{ url_for('admin') }}">Admin</a>
                {% endif %}
                <a href="{{ url_for('profile') }}">{{ user.username }}</a>
                <a href="{{ url_for('logout') }}">Đăng xuất</a>
            {% else %}
                <a href="{{ url_for('login') }}">Đăng nhập</a>
                <a href="{{ url_for('register') }}">Đăng ký</a>
            {% endif %}
        </div>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="flash {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endwith %}

        {{ content|safe }}
    </div>
</body>
</html>
"""

def render(title, content, user=None):
    return render_template_string(BASE, title=title, content=content, user=user)

# ==================== ROUTES ====================
@app.route("/")
def index():
    user = get_current_user()
    db = get_db()
    products = db.execute("""
        SELECT p.*, u.username, u.full_name, u.phone 
        FROM products p JOIN users u ON p.seller_id = u.id
        WHERE p.is_deleted = 0
        ORDER BY p.created_at DESC
    """).fetchall()

    content = """
    <h1 style="margin-bottom:20px;">Sản phẩm đang bán</h1>
    <div class="product-grid">
    """
    if not products:
        content += "<p>Chưa có sản phẩm nào.</p>"
    for p in products:
        content += f"""
        <div class="product-card">
            <div class="product-body">
                <h3>{p['title']}</h3>
                <p class="price">{p['price']:,} đ</p>
                <p style="color:#64748b; margin:8px 0;">{p['description'][:100]}{'...' if len(p['description'] or '') > 100 else ''}</p>
                <p><small>Người bán: <b>{p['full_name']}</b> (@{p['username']})</small></p>
                <p><small>SĐT: {p['phone']}</small></p>
            </div>
        </div>
        """
    content += "</div>"
    return render("Trang chủ", content, user)

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        cccd = request.form.get("cccd", "").strip()
        address = request.form.get("address", "").strip()
        phone = request.form.get("phone", "").strip()

        if not all([username, password, full_name, cccd, address, phone]):
            flash("Vui lòng điền đầy đủ thông tin!", "danger")
        else:
            db = get_db()
            try:
                hashed = generate_password_hash(password)
                db.execute("""
                    INSERT INTO users (username, password, full_name, cccd, address, phone, last_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (username, hashed, full_name, cccd, address, phone,
                      datetime.now().isoformat(), datetime.now().isoformat()))
                db.commit()
                flash("Đăng ký thành công! Hãy đăng nhập.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Tên đăng nhập đã tồn tại!", "danger")
    content = """
    <div class="card" style="max-width:480px;margin:0 auto;">
        <h2 style="margin-bottom:20px;">Đăng ký tài khoản</h2>
        <form method="POST">
            <label>Tên đăng nhập</label>
            <input name="username" required>
            <label>Mật khẩu</label>
            <input type="password" name="password" required>
            <label>Họ và tên</label>
            <input name="full_name" required>
            <label>CCCD / CMND</label>
            <input name="cccd" required>
            <label>Địa chỉ</label>
            <input name="address" required>
            <label>Số điện thoại</label>
            <input name="phone" required>
            <button class="btn btn-primary" style="width:100%;">Đăng ký</button>
        </form>
        <p style="margin-top:16px;text-align:center;">Đã có tài khoản? <a href="/login">Đăng nhập</a></p>
    </div>
    """
    return render("Đăng ký", content)

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password"], password):
            if user["is_banned"]:
                flash("Tài khoản của bạn đã bị cấm!", "danger")
            else:
                session["user_id"] = user["id"]
                update_last_active(user["id"])
                # Hiện thông báo chưa đọc
                notifs = db.execute("SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC",
                                    (user["id"],)).fetchall()
                if notifs:
                    for n in notifs:
                        flash(n["message"], "info")
                    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user["id"],))
                    db.commit()
                flash(f"Chào mừng trở lại, {user['full_name']}!", "success")
                return redirect(url_for("index"))
        else:
            flash("Sai tên đăng nhập hoặc mật khẩu!", "danger")
    content = """
    <div class="card" style="max-width:420px;margin:0 auto;">
        <h2 style="margin-bottom:20px;">Đăng nhập</h2>
        <form method="POST">
            <label>Tên đăng nhập</label>
            <input name="username" required>
            <label>Mật khẩu</label>
            <input type="password" name="password" required>
            <button class="btn btn-primary" style="width:100%;">Đăng nhập</button>
        </form>
        <p style="margin-top:16px;text-align:center;">Chưa có tài khoản? <a href="/register">Đăng ký ngay</a></p>
    </div>
    """
    return render("Đăng nhập", content)

@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("login"))

@app.route("/profile")
@login_required
def profile():
    user = get_current_user()
    content = f"""
    <div class="card">
        <h2>Thông tin cá nhân</h2>
        <p><b>Tên đăng nhập:</b> {user['username']}</p>
        <p><b>Họ tên:</b> {user['full_name']}</p>
        <p><b>CCCD:</b> {user['cccd']}</p>
        <p><b>Địa chỉ:</b> {user['address']}</p>
        <p><b>SĐT:</b> {user['phone']}</p>
        <p><b>Ngày tạo:</b> {user['created_at'][:19]}</p>
    </div>
    """
    return render("Hồ sơ", content, user)

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user = get_current_user()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0")
        try:
            price = int(price)
            if price <= 0:
                raise ValueError
        except:
            flash("Giá phải là số nguyên dương!", "danger")
            return redirect(url_for("sell"))
        if not title:
            flash("Tiêu đề không được để trống!", "danger")
        else:
            db = get_db()
            db.execute("""
                INSERT INTO products (seller_id, title, description, price, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user["id"], title, description, price, datetime.now().isoformat()))
            db.commit()
            flash("Đăng bán thành công!", "success")
            return redirect(url_for("index"))
    content = """
    <div class="card" style="max-width:560px;">
        <h2 style="margin-bottom:20px;">Đăng bán sản phẩm</h2>
        <form method="POST">
            <label>Tiêu đề sản phẩm</label>
            <input name="title" required>
            <label>Mô tả</label>
            <textarea name="description" rows="4"></textarea>
            <label>Giá (VNĐ)</label>
            <input type="number" name="price" required min="1000">
            <button class="btn btn-success">Đăng bán</button>
        </form>
    </div>
    """
    return render("Đăng bán", content, user)

@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    user = get_current_user()
    db = get_db()
    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if msg:
            db.execute("INSERT INTO chat_messages (user_id, message, created_at) VALUES (?, ?, ?)",
                       (user["id"], msg, datetime.now().isoformat()))
            db.commit()
        return redirect(url_for("chat"))

    messages = db.execute("""
        SELECT c.*, u.username, u.full_name 
        FROM chat_messages c JOIN users u ON c.user_id = u.id
        ORDER BY c.created_at DESC LIMIT 50
    """).fetchall()
    messages = list(reversed(messages))

    content = """
    <div class="card">
        <h2 style="margin-bottom:16px;">Chat chung</h2>
        <div class="chat-box" id="chatbox">
    """
    for m in messages:
        content += f"""
        <div class="msg">
            <span class="author">{m['full_name']} (@{m['username']})</span>
            <span class="time"> · {m['created_at'][11:16]}</span>
            <div style="margin-top:4px;">{m['message']}</div>
        </div>
        """
    content += """
        </div>
        <form method="POST" style="display:flex;gap:10px;">
            <input name="message" placeholder="Nhập tin nhắn..." required style="margin:0;flex:1;">
            <button class="btn btn-primary">Gửi</button>
        </form>
    </div>
    <script>
        const box = document.getElementById('chatbox');
        box.scrollTop = box.scrollHeight;
    </script>
    """
    return render("Chat chung", content, user)

# ==================== ADMIN ====================
@app.route("/admin")
@admin_required
def admin():
    user = get_current_user()
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    products = db.execute("""
        SELECT p.*, u.username, u.full_name 
        FROM products p JOIN users u ON p.seller_id = u.id
        WHERE p.is_deleted = 0
        ORDER BY p.created_at DESC
    """).fetchall()

    content = f"""
    <h1 style="margin-bottom:24px;">Trang Quản trị - TheOrders</h1>

    <div class="card">
        <h2>Quản lý tài khoản</h2>
        <table>
            <tr>
                <th>ID</th><th>Username</th><th>Họ tên</th><th>SĐT</th><th>Trạng thái</th><th>Hành động</th>
            </tr>
    """
    for u in users:
        status = '<span style="color:#dc2626;font-weight:700;">ĐÃ CẤM</span>' if u["is_banned"] else '<span style="color:#16a34a;">Hoạt động</span>'
        action = f'<a href="/admin/ban/{u["id"]}" class="btn btn-danger" style="padding:6px 12px;font-size:13px;">Cấm</a>' if not u["is_banned"] and not u["is_admin"] else \
                 f'<a href="/admin/unban/{u["id"]}" class="btn btn-success" style="padding:6px 12px;font-size:13px;">Bỏ cấm</a>' if u["is_banned"] else "Admin"
        content += f"""
            <tr>
                <td>{u['id']}</td>
                <td>{u['username']}</td>
                <td>{u['full_name']}</td>
                <td>{u['phone']}</td>
                <td>{status}</td>
                <td>{action}</td>
            </tr>
        """
    content += """
        </table>
    </div>

    <div class="card">
        <h2>Quản lý sản phẩm đang bán</h2>
        <table>
            <tr>
                <th>ID</th><th>Tiêu đề</th><th>Giá</th><th>Người bán</th><th>Hành động</th>
            </tr>
    """
    for p in products:
        content += f"""
            <tr>
                <td>{p['id']}</td>
                <td>{p['title']}</td>
                <td>{p['price']:,} đ</td>
                <td>{p['full_name']} (@{p['username']})</td>
                <td>
                    <form method="POST" action="/admin/delete_product/{p['id']}" style="display:inline;">
                        <input name="reason" placeholder="Lý do xóa..." required style="width:180px;margin:0;padding:6px;">
                        <button class="btn btn-danger" style="padding:6px 12px;font-size:13px;">Xóa</button>
                    </form>
                </td>
            </tr>
        """
    content += """
        </table>
    </div>
    """
    return render("Admin", content, user)

@app.route("/admin/ban/<int:uid>")
@admin_required
def ban_user(uid):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if user and not user["is_admin"]:
        db.execute("UPDATE users SET is_banned = 1 WHERE id = ?", (uid,))
        db.commit()
        add_notification(uid, "Tài khoản của bạn đã bị cấm bởi quản trị viên.")
        flash(f"Đã cấm tài khoản {user['username']}", "success")
    return redirect(url_for("admin"))

@app.route("/admin/unban/<int:uid>")
@admin_required
def unban_user(uid):
    db = get_db()
    db.execute("UPDATE users SET is_banned = 0 WHERE id = ?", (uid,))
    db.commit()
    add_notification(uid, "Tài khoản của bạn đã được mở khóa.")
    flash("Đã bỏ cấm tài khoản", "success")
    return redirect(url_for("admin"))

@app.route("/admin/delete_product/<int:pid>", methods=["POST"])
@admin_required
def delete_product(pid):
    reason = request.form.get("reason", "Không có lý do").strip()
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if product:
        db.execute("UPDATE products SET is_deleted = 1, delete_reason = ? WHERE id = ?", (reason, pid))
        db.commit()
        add_notification(product["seller_id"],
                         f"Sản phẩm '{product['title']}' của bạn đã bị xóa. Lý do: {reason}")
        flash("Đã xóa sản phẩm và gửi thông báo cho người bán", "success")
    return redirect(url_for("admin"))

# ==================== START ====================
if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    with app.app_context():
        init_db()
    print("=" * 50)
    print("  TheOrders đang chạy tại http://127.0.0.1:5000")
    print("  Admin: /admin  |  user: admin  |  pass: thanhtuan9988")
    print("  Hãy chạy ngrok http 5000 để public")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)