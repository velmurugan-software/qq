from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import time
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# Temporary server-side storage.
# Note: this resets when the Flask process restarts.
vault_items = []


def cleanup_expired():
    global vault_items
    now = int(time.time() * 1000)
    vault_items = [item for item in vault_items if item["expiresAt"] > now]


@app.route("/")
def index():
    cleanup_expired()
    return render_template("index.html")


@app.route("/api/items", methods=["GET"])
def get_items():
    cleanup_expired()
    return jsonify(vault_items)


@app.route("/api/items", methods=["POST"])
def create_item():
    cleanup_expired()

    title = request.form.get("title", "").strip()
    item_type = request.form.get("type", "code")
    language = request.form.get("language", "javascript")
    code = request.form.get("code", "")
    tags_text = request.form.get("tags", "")

    try:
        hours = int(request.form.get("hours", 0))
        minutes = int(request.form.get("minutes", 0))
    except ValueError:
        return jsonify({"error": "Invalid expiration duration."}), 400

    if not title:
        return jsonify({"error": "Title is required."}), 400

    if hours < 0 or minutes < 0 or minutes > 59:
        return jsonify({"error": "Invalid hours or minutes."}), 400

    duration_ms = ((hours * 60) + minutes) * 60 * 1000

    if duration_ms <= 0:
        return jsonify({
            "error": "Expiration time must be greater than 0 minutes."
        }), 400

    if item_type not in ("code", "image", "file"):
        return jsonify({"error": "Invalid item type."}), 400

    tags = [
        tag.strip().lower()
        for tag in tags_text.split(",")
        if tag.strip()
    ]

    file_name = None
    file_url = None

    if item_type in ("image", "file"):
        uploaded_file = request.files.get("file")

        if not uploaded_file or uploaded_file.filename == "":
            return jsonify({"error": "Please select a file."}), 400

        original_name = os.path.basename(uploaded_file.filename)
        extension = os.path.splitext(original_name)[1]
        stored_name = f"{uuid.uuid4().hex}{extension}"

        uploaded_file.save(
            os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
        )

        file_name = original_name
        file_url = f"/uploads/{stored_name}"

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

    vault_items.insert(0, item)

    return jsonify({
        "message": "Item saved successfully.",
        "item": item
    }), 201


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    global vault_items

    item = next(
        (item for item in vault_items if item["id"] == item_id),
        None
    )

    if item is None:
        return jsonify({"error": "Item not found."}), 404

    vault_items = [
        item for item in vault_items
        if item["id"] != item_id
    ]

    return jsonify({"message": "Item deleted successfully."})


@app.route("/api/clear-expired", methods=["DELETE"])
def clear_expired():
    global vault_items

    before = len(vault_items)
    cleanup_expired()
    removed = before - len(vault_items)

    return jsonify({
        "message": f"{removed} expired item(s) removed."
    })


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
