import os
from app import create_app  # <-- use the one from __init__.py

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render provides PORT
    app.run(host="0.0.0.0", port=port, debug=True)  # must bind to 0.0.0.0