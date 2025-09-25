from app import create_app  # <-- use the one from __init__.py

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
