from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # Register the blueprint (this handles all your routes)
    from routes import main
    app.register_blueprint(main)
    
    return app

# Create the app
app = create_app()

if __name__ == "__main__":

    app.run(debug=True) 