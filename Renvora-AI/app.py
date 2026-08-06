from flask import Flask, redirect
from config import Config
from models.user import db
from routes.auth import auth
from routes.project import project
from routes.chat import chat
from routes.admin import admin
from routes.setup import setup
from routes.knowledge import knowledge

app = Flask(__name__)

# Load Configuration
app.config.from_object(Config)

# Initialize Database
db.init_app(app)

# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(project)
app.register_blueprint(chat)
app.register_blueprint(admin)
app.register_blueprint(setup)
app.register_blueprint(knowledge)


# Default Route
@app.route("/")
def home():
    return redirect("/login")


# Run Application
if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )