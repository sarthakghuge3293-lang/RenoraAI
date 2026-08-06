from flask import Flask, redirect
from flask_cors import CORS
from config import Config
from models.user import db
from routes.auth import auth
from routes.project import project
from routes.chat import chat
from routes.admin import admin
from routes.setup import setup
from routes.user_pdf import user_pdf
from routes.pdf_ai import pdf_ai
from routes.mobile_api import mobile_api
from models.user_document import UserDocument

app = Flask(__name__)

# Load Configuration
app.config.from_object(Config)

# Enable CORS for Flutter mobile app (allow all origins in dev)
CORS(app, supports_credentials=True, resources={r"/mobile/*": {"origins": "*"}})

# Initialize Database
db.init_app(app)

# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(project)
app.register_blueprint(chat)
app.register_blueprint(admin)
app.register_blueprint(setup)

app.register_blueprint(user_pdf)
app.register_blueprint(pdf_ai)
app.register_blueprint(mobile_api)

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