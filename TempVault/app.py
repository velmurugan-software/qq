from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import time
import uuid

app = Flask(__name__)

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB


# --------------------------------------------------
# Temporary in-memory storage
# --------------------------------------------------

vault_items = []


# --------------------------------------------------
# Helper: Remove expired items
# --------------------------------------------------

def cleanup_expired():
    global vault_items

    now = int(time.time() * 1000)

    expired_items = [
        item for item in vault_items
        if item["expiresAt"] <= now
    ]

    # Delete uploaded files belonging to expired items
    for item in expired_items:
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

    vault_items = [
        item for item in vault_items
        if item["expiresAt"] > now
    ]


# --------------------------------------------------
# Home page
# --------------------------------------------------

@app.route("/")
def index():
    cleanup_expired()
    return render_template("index.html")


# --------------------------------------------------
# Get all active items
# --------------------------------------------------

@app.route("/api/items", methods=["GET"])
def get_items():
    cleanup_expired()

    return jsonify(vault_items)


# --------------------------------------------------
# Create new item
# --------------------------------------------------

@app.route("/api/items", methods=["POST"])
def create_item():
    cleanup_expired()

    # Get form values
    title = request.form.get("title", "").strip()
    item_type = request.form.get("type", "code").strip().lower()
    language = request.form.get(
        "language",
        "javascript"
    ).strip()

    code = request.form.get("code", "")
    tags_text = request.form.get("tags", "")

    # --------------------------------------------------
    # Validate title
    # --------------------------------------------------

    if not title:
        return jsonify({
            "error": "Title is required."
        }), 400

    # --------------------------------------------------
    # Validate item type
    # --------------------------------------------------

    allowed_types = {
        "code",
        "image",
        "file"
    }

    if item_type not in allowed_types:
        return jsonify({
            "error": "Invalid item type."
        }), 400

    # --------------------------------------------------
    # Get expiration time
    # --------------------------------------------------

    try:
        hours = int(request.form.get("hours", 0))
        minutes = int(request.form.get("minutes", 0))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid expiration duration."
        }), 400

    # --------------------------------------------------
    # Validate expiration
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Process tags
    # --------------------------------------------------

    tags = [
        tag.strip().lower()
        for tag in tags_text.split(",")
        if tag.strip()
    ]

    # --------------------------------------------------
    # File information
    # --------------------------------------------------

    file_name = None
    file_url = None

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

        # Original filename
        original_name = os.path.basename(
            uploaded_file.filename
        )

        # Get extension
        extension = os.path.splitext(
            original_name
        )[1]

        # Generate unique filename
        stored_name = (
            f"{uuid.uuid4().hex}"
            f"{extension}"
        )

        # Full save path
        save_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            stored_name
        )

        # Save uploaded file
        uploaded_file.save(save_path)

        file_name = original_name
        file_url = f"/uploads/{stored_name}"

    # --------------------------------------------------
    # Create item
    # --------------------------------------------------

    now = int(time.time() * 1000)

    item = {
        "id": now,
        "title": title,
        "type": item_type,
        "language": language,
        "tags": tags,
        "code": code if item_type == "code" else "",
        "fileData": file_url,
        "fileName": file_name,
        "expiresAt": now + duration_ms
    }

    # Add newest item at beginning
    vault_items.insert(0, item)

    return jsonify({
        "message": "Item saved successfully.",
        "item": item
    }), 201


# --------------------------------------------------
# Delete item
# --------------------------------------------------

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

    # Remove item from memory
    vault_items = [
        item
        for item in vault_items
        if item["id"] != item_id
    ]

    return jsonify({
        "message": "Item deleted successfully."
    })


# --------------------------------------------------
# Clear expired items
# --------------------------------------------------

@app.route(
    "/api/clear-expired",
    methods=["DELETE"]
)
def clear_expired():

    before = len(vault_items)

    cleanup_expired()

    removed = (
        before - len(vault_items)
    )

    return jsonify({
        "message": (
            f"{removed} expired item(s) removed."
        )
    })


# --------------------------------------------------
# Serve uploaded files
# --------------------------------------------------

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# --------------------------------------------------
# Error: File too large
# --------------------------------------------------

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "error": "File is too large. Maximum size is 16 MB."
    }), 413


# --------------------------------------------------
# Run locally
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
