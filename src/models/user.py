from .database import db, BaseModel
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import enum

class UserType(enum.Enum):
    CUSTOMER = 'customer'
    SELLER = 'seller'
    ADMIN = 'admin'

class User(BaseModel):
    __tablename__ = 'users'
    
    # Basic Information
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    
    # User Type and Status
    user_type = db.Column(db.Enum(UserType), nullable=False, default=UserType.CUSTOMER)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Profile Information
    profile_picture_url = db.Column(db.Text, nullable=True)
    preferred_language = db.Column(db.String(5), default='ar', nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    addresses = db.relationship('UserAddress', backref='user', lazy=True, cascade='all, delete-orphan')
    pharmacy = db.relationship('Pharmacy', backref='seller', uselist=False, cascade='all, delete-orphan')
    shopping_cart = db.relationship('ShoppingCart', backref='user', uselist=False, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', lazy=True)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary, optionally excluding sensitive data"""
        data = super().to_dict()
        if not include_sensitive:
            data.pop('password_hash', None)
            data.pop('verification_token', None)
        data['full_name'] = self.get_full_name()
        data['user_type'] = self.user_type.value if self.user_type else None
        return data
    
    def __repr__(self):
        return f'<User {self.email}>'

class UserAddress(BaseModel):
    __tablename__ = 'user_addresses'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Location Information
    country = db.Column(db.String(100), default='Yemen', nullable=False)
    city = db.Column(db.String(100), default='Taiz', nullable=False)
    district = db.Column(db.String(100), nullable=False)
    detailed_address = db.Column(db.Text, nullable=True)
    
    # Coordinates
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    # Status
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['latitude'] = float(data['latitude']) if data['latitude'] else None
        data['longitude'] = float(data['longitude']) if data['longitude'] else None
        return data
    
    def __repr__(self):
        return f'<UserAddress {self.district}, {self.city}>'
