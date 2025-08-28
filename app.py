from flask import Flask, render_template

def create_app():
    app = Flask(__name__)

    @app.route('/')
    def home():
        return render_template('index.html')

    return app

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)