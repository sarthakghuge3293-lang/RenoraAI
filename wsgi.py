from app import app
from models.user import db

# Ensure database tables are created before starting the server
# Useful for Render deployments
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
