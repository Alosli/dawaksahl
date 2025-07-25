from .database import db, BaseModel
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import enum
import secrets

class UserType(enum.Enum):
    CUSTOMER = 'customer'
    SELLER = 'seller'
    ADMIN = 'admin'

class User(BaseModel):
    __tablename__ = 'users'
    
    # Basic Information
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    first_name_ar = db.Column(db.String(100), nullable=True)
    last_name_ar = db.Column(db.String(100), nullable=True)
    
    # User Type and Status
    user_type = db.Column(db.Enum(UserType), nullable=False, default=UserType.CUSTOMER)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Email Verification
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    email_verification_token = db.Column(db.String(255), nullable=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Password Reset
    password_reset_token = db.Column(db.String(255), nullable=True)
    password_reset_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Profile Information
    profile_picture_url = db.Column(db.Text, nullable=True)
    preferred_language = db.Column(db.String(5), default='en', nullable=False)
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
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_full_name_ar(self):
        """Get user's full name in Arabic"""
        if self.first_name_ar and self.last_name_ar:
            return f"{self.first_name_ar} {self.last_name_ar}".strip()
        return self.get_full_name()
    
    def generate_verification_token(self):
        """Generate email verification token"""
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_sent_at = datetime.utcnow()
    
    def generate_password_reset_token(self):
        """Generate password reset token"""
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_sent_at = datetime.utcnow()
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary, optionally excluding sensitive data"""
        data = super().to_dict()
        if not include_sensitive:
            data.pop('password_hash', None)
            data.pop('email_verification_token', None)
            data.pop('password_reset_token', None)
        data['full_name'] = self.get_full_name()
        data['full_name_ar'] = self.get_full_name_ar()
        data['user_type'] = self.user_type.value if self.user_type else None
        return data
    
    def __repr__(self):
        return f'<User {self.email}>'

class UserAddress(BaseModel):
    __tablename__ = 'user_addresses'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Address Information
    label = db.Column(db.String(50), default='Home', nullable=False)
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255), nullable=True)
    district_id = db.Column(db.Integer, db.ForeignKey('districts.id'), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    # Coordinates
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    # Status
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['latitude'] = float(data['latitude']) if data['latitude'] else None
        data['longitude'] = float(data['longitude']) if data['longitude'] else None
        return data
    
    def __repr__(self):
        return f'<UserAddress {self.label}: {self.address_line1}>'
