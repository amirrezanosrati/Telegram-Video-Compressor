# server.py
import os
from flask import Flask, send_from_directory, abort

UPLOAD_FOLDER = "uploads"
app = Flask(__name__)

@app.route("/<path:filename>")
def serve_file(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.isfile(path):
        return abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route("/")
def index():
    return "File server is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
