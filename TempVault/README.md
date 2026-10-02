# TempVault - Flask

Temporary storage for text/code, images, and documents with automatic expiration.

## Features

- Add temporary code/text
- Add images
- Add document files
- Set expiration in hours and minutes
- Live countdown
- Automatically removes expired entries from the active list
- Search by title, content, filename, and tags
- Delete individual items
- Clear expired items
- 16 MB upload limit
- Flask backend

## Requirements

Python 3.10 or newer is recommended.

## Windows setup

Open Command Prompt inside the TempVault folder:

```bash
python -m venv venv
```

Activate the environment:

```bash
venv\Scripts\activate
```

Install packages:

```bash
pip install -r requirements.txt
```

Run:

```bash
python app.py
```

Open:

http://127.0.0.1:5000

## Important

The current version keeps item metadata in Python memory. Therefore, the items are cleared when the Flask server restarts.

Uploaded files are stored in the `uploads` folder.

For a production version, use SQLite/PostgreSQL for metadata and a proper file-storage strategy.
