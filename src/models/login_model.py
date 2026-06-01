from db.extention import db

class LoginModel(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'password': self.password
        }