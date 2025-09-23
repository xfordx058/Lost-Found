from flask import Flask, render_template, request, redirect, url_for, session, flash
import json, os, datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret123"   # for login sessions

ITEMS_FILE = "items.json"
STAFF_FILE = "staff.json"
USERS_FILE = "users.json"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# --- Make session available in all templates ---
@app.context_processor
def inject_session():
    return dict(session=session)

# --- Template Filter ---
@app.template_filter("format_datetime")
def format_datetime(value):
    try:
        dt = datetime.datetime.fromisoformat(value)
        return dt.strftime("%B %d, %Y %I:%M %p")
    except Exception:
        return value

# --- JSON Helpers ---
def load_json(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return []

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# --- Staff ---
def load_staff():
    return load_json(STAFF_FILE)

def save_staff(staff_list):
    save_json(STAFF_FILE, staff_list)

@app.route("/staff")
def staff():
    if "user_id" not in session:
        return redirect(url_for("login"))
    staff_list = load_staff()
    return render_template("staff.html", staff=staff_list)

@app.route("/staff/add", methods=["GET", "POST"])
def add_staff():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        staff_list = load_staff()
        new_staff = {
            "id": len(staff_list) + 1,
            "name": request.form["name"],
            "role": request.form["role"],
            "date_added": datetime.datetime.now().isoformat()
        }
        staff_list.append(new_staff)
        save_staff(staff_list)
        return redirect(url_for("staff"))
    return render_template("add_staff.html")

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Items ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_items():
    return load_json(ITEMS_FILE)

def save_items(items):
    save_json(ITEMS_FILE, items)

# --- Routes ---
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    query = request.args.get("q", "").lower()
    items = load_items()

    if query:
        items = [i for i in items if query in i["name"].lower() or query in i["category"].lower()]

    for item in items:
        date_found = datetime.datetime.fromisoformat(item["date_found"])
        now = datetime.datetime.now()
        delta = now - date_found

        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60

        if days > 0:
            item["time_stored"] = f"{days} day{'s' if days > 1 else ''} ago"
        elif hours > 0:
            item["time_stored"] = f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif minutes > 0:
            item["time_stored"] = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            item["time_stored"] = "Just now"

    return render_template("index.html", items=items, query=query)

@app.route("/add", methods=["GET", "POST"])
def add_item():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        items = load_items()
        file = request.files.get("image")
        filename = ""
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        item = {
            "id": len(items) + 1,
            "name": request.form["name"],
            "description": request.form["description"],
            "category": request.form["category"],
            "date_found": datetime.datetime.now().isoformat(),
            "status": "Unclaimed",
            "assisting_staff": "",
            "image": filename
        }
        items.append(item)
        save_items(items)
        return redirect(url_for("home"))
    return render_template("add_item.html")

# --- Update Item ---
@app.route("/update/<int:item_id>", methods=["GET", "POST"])
def update_item(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    items = load_items()
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return "Item not found", 404

    if request.method == "POST":
        item["name"] = request.form["name"]
        item["description"] = request.form["description"]
        item["category"] = request.form["category"]

        file = request.files.get("image")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            item["image"] = filename

        save_items(items)
        flash("Item updated successfully!", "success")
        return redirect(url_for("home"))

    return render_template("update_item.html", item=item)

# --- Claim Item ---
@app.route("/claim/<int:item_id>", methods=["GET", "POST"])
def claim_item(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    items = load_items()
    staff_list = load_staff()
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return "Item not found", 404

    if request.method == "POST":
        item["status"] = "Claimed"
        item["assisting_staff"] = request.form["staff"]
        item["claimer_name"] = request.form["claimer_name"]
        item["college"] = request.form["college"]
        item["course"] = request.form["course"]
        item["year_section"] = request.form["year_section"]
        item["claimed_at"] = datetime.datetime.now().strftime("%B %d, %Y %I:%M %p")

        file = request.files.get("proof")
        if file and allowed_file(file.filename):
            proof_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], proof_filename))
            item["proof_image"] = proof_filename
            item["proof_uploaded_at"] = datetime.datetime.now().isoformat()

        save_items(items)
        return redirect(url_for("home"))

    return render_template("claim_item.html", item=item, staff_list=staff_list)

@app.route("/delete/<int:item_id>")
def delete_item(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    items = load_items()
    items = [i for i in items if i["id"] != item_id]
    save_items(items)
    return redirect(url_for("home"))

# --- Login with Student ID only ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        student_id = request.form["student_id"]
        users = load_json(USERS_FILE)

        for user in users:
            if str(user.get("student_id")) == student_id:
                session["user_id"] = user["id"]
                flash("Login successful!", "success")
                return redirect(url_for("home"))

        flash("Invalid Student ID", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    return "Registration is disabled. Please contact admin to add users.", 403

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

app.run(debug=True)
