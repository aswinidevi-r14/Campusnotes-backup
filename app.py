from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder=".")

app.secret_key = "campusnotes_secret_key"

DATABASE = "database.db"


# ================= DATABASE =================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn



def create_demo_staff():

    conn = get_db()

    existing_staff = conn.execute("""
        SELECT id FROM users
        WHERE email = ?
    """, ("staff@campusnotes.com",)).fetchone()

    if not existing_staff:

        password = generate_password_hash("staff123")

        conn.execute("""
            INSERT INTO users
            (name, email, password, role)
            VALUES (?, ?, ?, ?)
        """, (
            "Faculty Admin",
            "staff@campusnotes.com",
            password,
            "staff"
        ))

        conn.commit()

    conn.close()
def init_db():

    conn = get_db()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # Notes table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            department TEXT NOT NULL,
            semester TEXT NOT NULL,
            subject TEXT NOT NULL,
            unit TEXT,
            filename TEXT NOT NULL,
            uploaded_by INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            rejection_reason TEXT,
            download_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (uploaded_by)
            REFERENCES users(id)
        )
    """)
    # Ratings and Reviews table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            review TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (note_id)
            REFERENCES notes(id),

            FOREIGN KEY (user_id)
            REFERENCES users(id),

            UNIQUE(note_id, user_id)
        )
    """)
    conn.commit()
    conn.close()


# ================= HOME =================

@app.route("/")
def home():
    return render_template("index.html")


# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO users
                (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (name, email, hashed_password, role))

            conn.commit()

            flash("Registration successful! Please login.")

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            flash("Email already registered.")

        finally:

            conn.close()

    return render_template("register.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            if user["role"] == "senior":
                return redirect(url_for("senior_dashboard"))

            elif user["role"] == "junior":
                return redirect(url_for("junior_dashboard"))

            elif user["role"] == "staff":
                return redirect(url_for("staff_dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")

# ================= UPLOAD NOTES =================

@app.route("/senior/upload", methods=["GET", "POST"])
def upload_note():

    if session.get("role") != "senior":
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        department = request.form["department"]
        semester = request.form["semester"]
        subject = request.form["subject"]
        unit = request.form["unit"]

        file = request.files["file"]

        if file.filename == "":
            flash("Please select a PDF file.")
            return redirect(url_for("upload_note"))

        # Allow only PDF files
        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are allowed.")
            return redirect(url_for("upload_note"))

        # Create uploads folder
        import os

        upload_folder = os.path.join(
            app.root_path,
            "static",
            "uploads"
        )

        os.makedirs(upload_folder, exist_ok=True)

        filename = file.filename

        file.save(
            os.path.join(
                upload_folder,
                filename
            )
        )

        conn = get_db()

        conn.execute("""
            INSERT INTO notes
            (
                title,
                description,
                department,
                semester,
                subject,
                unit,
                filename,
                uploaded_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            description,
            department,
            semester,
            subject,
            unit,
            filename,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        flash(
            "Note uploaded successfully! Waiting for staff approval."
        )

        return redirect(
            url_for("senior_dashboard")
        )

    return render_template("upload.html")


# ================= DASHBOARDS =================

@app.route("/senior/dashboard")
def senior_dashboard():

    if session.get("role") != "senior":
        return redirect(url_for("login"))

    conn = get_db()

    # Get senior's uploaded notes
    notes = conn.execute("""
        SELECT *
        FROM notes
        WHERE uploaded_by = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    # Dashboard statistics
    total = conn.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE uploaded_by = ?
    """, (session["user_id"],)).fetchone()[0]

    approved = conn.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE uploaded_by = ?
        AND status = 'approved'
    """, (session["user_id"],)).fetchone()[0]

    pending = conn.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE uploaded_by = ?
        AND status = 'pending'
    """, (session["user_id"],)).fetchone()[0]

    rejected = conn.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE uploaded_by = ?
        AND status = 'rejected'
    """, (session["user_id"],)).fetchone()[0]

    downloads = conn.execute("""
        SELECT COALESCE(SUM(download_count), 0)
        FROM notes
        WHERE uploaded_by = ?
    """, (session["user_id"],)).fetchone()[0]

    conn.close()

    return render_template(
        "senior_dashboard.html",
        name=session.get("name"),
        notes=notes,
        total=total,
        approved=approved,
        pending=pending,
        rejected=rejected,
        downloads=downloads
    )   

@app.route("/junior/dashboard")
def junior_dashboard():

    if session.get("role") != "junior":
        return redirect(url_for("login"))

    conn = get_db()

    notes = conn.execute("""
        SELECT
            notes.*,
            users.name AS uploader_name
        FROM notes
        JOIN users
        ON notes.uploaded_by = users.id
        WHERE notes.status = 'approved'
        ORDER BY notes.created_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        "junior_dashboard.html",
        name=session.get("name"),
        notes=notes
    )
# ================= NOTE DETAILS =================

@app.route("/note/<int:note_id>")
def note_details(note_id):

    if session.get("role") != "junior":
        return redirect(url_for("login"))

    conn = get_db()

    note = conn.execute("""
        SELECT
            notes.*,
            users.name AS uploader_name
        FROM notes
        JOIN users
        ON notes.uploaded_by = users.id
        WHERE notes.id = ?
        AND notes.status = 'approved'
    """, (note_id,)).fetchone()

    if not note:
        conn.close()
        flash("This resource is not available.")
        return redirect(url_for("junior_dashboard"))

    # Average rating
    average_rating = conn.execute("""
        SELECT ROUND(AVG(rating), 1)
        FROM ratings
        WHERE note_id = ?
    """, (note_id,)).fetchone()[0]

    # Number of reviews
    review_count = conn.execute("""
        SELECT COUNT(*)
        FROM ratings
        WHERE note_id = ?
    """, (note_id,)).fetchone()[0]

    # Reviews
    reviews = conn.execute("""
        SELECT
            ratings.*,
            users.name AS reviewer_name
        FROM ratings
        JOIN users
        ON ratings.user_id = users.id
        WHERE ratings.note_id = ?
        ORDER BY ratings.created_at DESC
    """, (note_id,)).fetchall()

    # Current user's rating
    my_rating = conn.execute("""
        SELECT *
        FROM ratings
        WHERE note_id = ?
        AND user_id = ?
    """, (note_id, session["user_id"])).fetchone()

    conn.close()

    return render_template(
        "note_details.html",
        name=session.get("name"),
        note=note,
        average_rating=average_rating or 0,
        review_count=review_count,
        reviews=reviews,
        my_rating=my_rating
    )
# ================= SUBMIT RATING =================

@app.route("/note/<int:note_id>/rate", methods=["POST"])
def rate_note(note_id):

    if session.get("role") != "junior":
        return redirect(url_for("login"))

    rating = request.form.get("rating")
    review = request.form.get("review", "").strip()

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        flash("Please select a valid rating.")
        return redirect(url_for(
            "note_details",
            note_id=note_id
        ))

    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.")
        return redirect(url_for(
            "note_details",
            note_id=note_id
        ))

    conn = get_db()

    # Make sure note exists and is approved
    note = conn.execute("""
        SELECT id
        FROM notes
        WHERE id = ?
        AND status = 'approved'
    """, (note_id,)).fetchone()

    if not note:
        conn.close()
        flash("This resource is not available.")
        return redirect(url_for("junior_dashboard"))

    try:

        conn.execute("""
            INSERT INTO ratings
            (note_id, user_id, rating, review)
            VALUES (?, ?, ?, ?)
        """, (
            note_id,
            session["user_id"],
            rating,
            review
        ))

        flash("Thank you! Your rating has been added.")

    except sqlite3.IntegrityError:

        # User already rated this note
        conn.execute("""
            UPDATE ratings
            SET rating = ?,
                review = ?,
                created_at = CURRENT_TIMESTAMP
            WHERE note_id = ?
            AND user_id = ?
        """, (
            rating,
            review,
            note_id,
            session["user_id"]
        ))

        flash("Your rating has been updated.")

    conn.commit()
    conn.close()

    return redirect(url_for(
        "note_details",
        note_id=note_id
    ))
@app.route("/download/<int:note_id>")
def download_note(note_id):

    if session.get("role") != "junior":
        return redirect(url_for("login"))

    conn = get_db()

    note = conn.execute("""
        SELECT * FROM notes
        WHERE id = ?
        AND status = 'approved'
    """, (note_id,)).fetchone()

    if not note:
        conn.close()
        flash("This resource is not available.")
        return redirect(url_for("junior_dashboard"))

    # Increase download count
    conn.execute("""
        UPDATE notes
        SET download_count = download_count + 1
        WHERE id = ?
    """, (note_id,))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "static",
            filename="uploads/" + note["filename"]
        )
    )
@app.route("/staff/dashboard")
def staff_dashboard():

    if session.get("role") != "staff":
        return redirect(url_for("login"))

    conn = get_db()

    notes = conn.execute("""
        SELECT
            notes.*,
            users.name AS uploader_name
        FROM notes
        JOIN users
        ON notes.uploaded_by = users.id
        WHERE notes.status = 'pending'
        ORDER BY notes.created_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        "staff_dashboard.html",
        name=session.get("name"),
        notes=notes
    )
# ================= APPROVE NOTE =================

@app.route("/staff/approve/<int:note_id>")
def approve_note(note_id):

    if session.get("role") != "staff":
        return redirect(url_for("login"))

    conn = get_db()

    conn.execute("""
        UPDATE notes
        SET status = 'approved'
        WHERE id = ?
    """, (note_id,))

    conn.commit()
    conn.close()

    flash("Note approved successfully.")

    return redirect(
        url_for("staff_dashboard")
    )
# ================= REJECT NOTE =================
@app.route("/staff/reject/<int:note_id>", methods=["POST"])
def reject_note(note_id):

    if session.get("role") != "staff":
        return redirect(url_for("login"))

    reason = request.form.get("reason")

    if not reason:
        reason = "Please review and improve the uploaded resource."

    conn = get_db()

    conn.execute("""
        UPDATE notes
        SET status = 'rejected',
            rejection_reason = ?
        WHERE id = ?
    """, (reason, note_id))

    conn.commit()
    conn.close()

    flash("Note rejected and feedback sent to the senior.")

    return redirect(url_for("staff_dashboard"))

# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))

@app.route("/staff/analytics")
def staff_analytics():

    if session.get("role") != "staff":
        return redirect(url_for("login"))

    conn = get_db()

    # Total students
    total_students = conn.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE role IN ('junior', 'senior')
    """).fetchone()[0]

    # Total resources
    total_resources = conn.execute("""
        SELECT COUNT(*)
        FROM notes
    """).fetchone()[0]

    # Pending resources
    pending = conn.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE status = 'pending'
    """).fetchone()[0]

    # Approved resources
    approved = conn.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE status = 'approved'
    """).fetchone()[0]

    # Rejected resources
    rejected = conn.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE status = 'rejected'
    """).fetchone()[0]

    # Total downloads
    total_downloads = conn.execute("""
        SELECT COALESCE(SUM(download_count), 0)
        FROM notes
    """).fetchone()[0]

    # Top contributors
    contributors = conn.execute("""
        SELECT
            users.name,
            COUNT(notes.id) AS upload_count
        FROM notes
        JOIN users
        ON notes.uploaded_by = users.id
        GROUP BY notes.uploaded_by
        ORDER BY upload_count DESC
        LIMIT 5
    """).fetchall()

    # Most downloaded resources
    popular_notes = conn.execute("""
        SELECT
            title,
            subject,
            download_count
        FROM notes
        WHERE status = 'approved'
        ORDER BY download_count DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "staff_analytics.html",
        name=session.get("name"),
        total_students=total_students,
        total_resources=total_resources,
        pending=pending,
        approved=approved,
        rejected=rejected,
        total_downloads=total_downloads,
        contributors=contributors,
        popular_notes=popular_notes
    )

# ================= START =================


if __name__ == "__main__":

    init_db()

    create_demo_staff()

    import os
    port = int(os.environ.get("PORT" ,5000))
    app.run(
        host="0.0.0.0",
        port=port
    )
