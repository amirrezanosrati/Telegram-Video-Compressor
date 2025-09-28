from flask import Flask, send_from_directory, abort
import os

UPLOAD_FOLDER = "uploads"
app = Flask(__name__)

@app.route("/<filename>")
def serve_file(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path):
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
    else:
        abort(404, "File not found")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
