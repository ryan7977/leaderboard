from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

db = SQLAlchemy()

class SalesData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    demos = db.Column(db.Integer, nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        logger.debug(f"Password hash set: {self.password_hash}")

    def check_password(self, password):
        result = check_password_hash(self.password_hash, password)
        logger.debug(f"Password check result: {result}")
        return result

    @classmethod
    def get_admin(cls):
        admin = cls.query.get(1)
        logger.debug(f"Admin user retrieved: {admin}")
        return admin
