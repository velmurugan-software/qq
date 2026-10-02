from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory
)
import os
import sqlite3
import uuid

app = Flask(__name__)

# ============================================================
# Configuration
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATABASE = os.path.join(BASE_DIR, "vault.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


# ============================================================
# Database connection
# ============================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# Create database
# ============================================================

def init_database():

    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS vault_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            item_type TEXT NOT NULL,
            language TEXT,
            tags TEXT,
            code TEXT,
            file_data TEXT,
            file_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


# ============================================================
# Home page
# ============================================================

@app.route("/")
def index():

    return render_template("index.html")


# ============================================================
# Get all items
# ============================================================

@app.route("/api/items", methods=["GET"])
def get_items():

    connection = get_db()

    rows = connection.execute("""
        SELECT *
        FROM vault_items
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    items = []

    for row in rows:

        tags = []

        if row["tags"]:
            tags = [
                tag.strip()
                for tag in row["tags"].split(",")
                if tag.strip()
            ]

        items.append({
            "id": row["id"],
            "title": row["title"],
            "type": row["item_type"],
            "language": row["language"],
            "tags": tags,
            "code": row["code"] or "",
            "fileData": row["file_data"],
            "fileName": row["file_name"],
            "createdAt": row["created_at"]
        })

    return jsonify(items)


# ============================================================
# Create new item
# ============================================================

@app.route("/api/items", methods=["POST"])
def create_item():

    title = request.form.get(
        "title",
        ""
    ).strip()

    item_type = request.form.get(
        "type",
        "code"
    ).strip().lower()

    language = request.form.get(
        "language",
        "javascript"
    ).strip()

    code = request.form.get(
        "code",
        ""
    )

    tags_text = request.form.get(
        "tags",
        ""
    )

    # --------------------------------------------------------
    # Validate title
    # --------------------------------------------------------

    if not title:

        return jsonify({
            "error": "Title is required."
        }), 400

    # --------------------------------------------------------
    # Validate type
    # --------------------------------------------------------

    allowed_types = {
        "code",
        "image",
        "file"
    }

    if item_type not in allowed_types:

        return jsonify({
            "error": "Invalid item type."
        }), 400

    # --------------------------------------------------------
    # Process tags
    # --------------------------------------------------------

    tags = [
        tag.strip().lower()
        for tag in tags_text.split(",")
        if tag.strip()
    ]

    tags_string = ",".join(tags)

    file_name = None
    file_url = None

    # --------------------------------------------------------
    # Handle image/file upload
    # --------------------------------------------------------

    if item_type in ("image", "file"):

        uploaded_file = request.files.get("file")

        if not uploaded_file:

            return jsonify({
                "error": "Please select a file."
            }), 400

        if uploaded_file.filename == "":

            return jsonify({
                "error": "Please select a file."
            }), 400

        # Get original filename
        original_name = os.path.basename(
            uploaded_file.filename
        )

        # Get extension
        extension = os.path.splitext(
            original_name
        )[1]

        # Generate unique filename
        stored_name = (
            uuid.uuid4().hex
            + extension
        )

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            stored_name
        )

        # Save file
        uploaded_file.save(file_path)

        file_name = original_name

        file_url = (
            "/uploads/"
            + stored_name
        )

    # --------------------------------------------------------
    # Save to database
    # --------------------------------------------------------

    connection = get_db()

    cursor = connection.execute("""
        INSERT INTO vault_items (
            title,
            item_type,
            language,
            tags,
            code,
            file_data,
            file_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        item_type,
        language,
        tags_string,
        code if item_type == "code" else "",
        file_url,
        file_name
    ))

    connection.commit()

    item_id = cursor.lastrowid

    connection.close()

    # --------------------------------------------------------
    # Return created item
    # --------------------------------------------------------

    return jsonify({
        "message": "Item saved successfully.",
        "item": {
            "id": item_id,
            "title": title,
            "type": item_type,
            "language": language,
            "tags": tags,
            "code": code if item_type == "code" else "",
            "fileData": file_url,
            "fileName": file_name
        }
    }), 201


# ============================================================
# Delete item
# ============================================================

@app.route(
    "/api/items/<int:item_id>",
    methods=["DELETE"]
)
def delete_item(item_id):

    connection = get_db()

    row = connection.execute("""
        SELECT *
        FROM vault_items
        WHERE id = ?
    """, (item_id,)).fetchone()

    if row is None:

        connection.close()

        return jsonify({
            "error": "Item not found."
        }), 404

    # --------------------------------------------------------
    # Delete uploaded file
    # --------------------------------------------------------

    file_data = row["file_data"]

    if file_data:

        filename = os.path.basename(
            file_data
        )

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        if os.path.exists(file_path):

            try:
                os.remove(file_path)

            except OSError:
                pass

    # --------------------------------------------------------
    # Delete database record
    # --------------------------------------------------------

    connection.execute("""
        DELETE FROM vault_items
        WHERE id = ?
    """, (item_id,))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Item deleted successfully."
    })


# ============================================================
# Serve uploaded files
# ============================================================

@app.route(
    "/uploads/<path:filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ============================================================
# File too large
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "error": "File is too large. Maximum size is 16 MB."
    }), 413


# ============================================================
# Initialize database
# ============================================================

init_database()


# ============================================================
# Local development
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
