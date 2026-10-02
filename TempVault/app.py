from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import time
import uuid

app = Flask(__name__)

# ============================================================
# Configuration
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB


# ============================================================
# Temporary storage
# ============================================================

vault_items = []


# ============================================================
# Remove expired items
# ============================================================

def cleanup_expired():
    global vault_items

    current_time = int(time.time() * 1000)

    active_items = []

    for item in vault_items:

        if item["expiresAt"] > current_time:
            active_items.append(item)

        else:
            # Delete uploaded file if it exists
            file_url = item.get("fileData")

            if file_url and file_url.startswith("/uploads/"):

                filename = os.path.basename(file_url)

                file_path = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )

                if os.path.exists(file_path):

                    try:
                        os.remove(file_path)

                    except OSError:
                        pass

    vault_items = active_items


# ============================================================
# Home page
# ============================================================

@app.route("/")
def index():

    cleanup_expired()

    return render_template("index.html")


# ============================================================
# Get items
# ============================================================

@app.route("/api/items", methods=["GET"])
def get_items():

    cleanup_expired()

    return jsonify(vault_items)


# ============================================================
# Create item
# ============================================================

@app.route("/api/items", methods=["POST"])
def create_item():

    cleanup_expired()

    # --------------------------------------------------------
    # Get form data
    # --------------------------------------------------------

    title = request.form.get("title", "").strip()

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
    # Get expiration
    # --------------------------------------------------------

    try:

        hours = int(
            request.form.get(
                "hours",
                0
            )
        )

        minutes = int(
            request.form.get(
                "minutes",
                0
            )
        )

    except (ValueError, TypeError):

        return jsonify({
            "error": "Invalid expiration duration."
        }), 400

    # --------------------------------------------------------
    # Validate expiration
    # --------------------------------------------------------

    if hours < 0:

        return jsonify({
            "error": "Hours cannot be negative."
        }), 400

    if minutes < 0 or minutes > 59:

        return jsonify({
            "error": "Minutes must be between 0 and 59."
        }), 400

    duration_ms = (
        (hours * 60 + minutes)
        * 60
        * 1000
    )

    if duration_ms <= 0:

        return jsonify({
            "error": "Expiration time must be greater than 0 minutes."
        }), 400

    # --------------------------------------------------------
    # Process tags
    # --------------------------------------------------------

    tags = [
        tag.strip().lower()
        for tag in tags_text.split(",")
        if tag.strip()
    ]

    # --------------------------------------------------------
    # File variables
    # --------------------------------------------------------

    file_name = None
    file_url = None

    # --------------------------------------------------------
    # Upload file
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

        # Full file path
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
    # Create item
    # --------------------------------------------------------

    current_time = int(
        time.time() * 1000
    )

    item = {
        "id": current_time,

        "title": title,

        "type": item_type,

        "language": language,

        "tags": tags,

        "code": (
            code
            if item_type == "code"
            else ""
        ),

        "fileData": file_url,

        "fileName": file_name,

        "expiresAt": (
            current_time
            + duration_ms
        )
    }

    # Add newest item first
    vault_items.insert(
        0,
        item
    )

    return jsonify({
        "message": "Item saved successfully.",
        "item": item
    }), 201


# ============================================================
# Delete item
# ============================================================

@app.route(
    "/api/items/<int:item_id>",
    methods=["DELETE"]
)
def delete_item(item_id):

    global vault_items

    cleanup_expired()

    item = next(
        (
            item
            for item in vault_items
            if item["id"] == item_id
        ),
        None
    )

    if item is None:

        return jsonify({
            "error": "Item not found."
        }), 404

    # Delete associated file
    file_url = item.get(
        "fileData"
    )

    if file_url and file_url.startswith(
        "/uploads/"
    ):

        filename = os.path.basename(
            file_url
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

    # Remove item
    vault_items = [
        item
        for item in vault_items
        if item["id"] != item_id
    ]

    return jsonify({
        "message": "Item deleted successfully."
    })


# ============================================================
# Clear expired items
# ============================================================

@app.route(
    "/api/clear-expired",
    methods=["DELETE"]
)
def clear_expired():

    before = len(vault_items)

    cleanup_expired()

    removed = (
        before
        - len(vault_items)
    )

    return jsonify({
        "message": (
            f"{removed} expired item(s) removed."
        )
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
# File too large error
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "error": "File is too large. Maximum size is 16 MB."
    }), 413


# ============================================================
# Local development
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
