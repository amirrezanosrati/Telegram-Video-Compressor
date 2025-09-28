from flask import Flask, send_from_directory
import os

UPLOAD_FOLDER = "uploads"
app = Flask(__name__)

@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/")
def home():
    return "🤖 File Server is Running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
