from .database import db, BaseModel
from datetime import datetime, time
import enum

class PharmacyStatus(enum.Enum):
    PENDING = 'pending'
    VERIFIED = 'verified'
    SUSPENDED = 'suspended'
    REJECTED = 'rejected'

class Pharmacy(BaseModel):
    __tablename__ = 'pharmacies'
    
    # Owner Information
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Basic Information
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    description_ar = db.Column(db.Text, nullable=True)
    
    # Contact Information
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    
    # Location Information
    address = db.Column(db.Text, nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey('districts.id'), nullable=False)
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    # Business Information
    license_number = db.Column(db.String(100), unique=True, nullable=True)
    tax_number = db.Column(db.String(100), nullable=True)
    
    # Status and Verification
    status = db.Column(db.Enum(PharmacyStatus), default=PharmacyStatus.PENDING, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_date = db.Column(db.DateTime, nullable=True)
    
    # Service Information
    delivery_available = db.Column(db.Boolean, default=False, nullable=False)
    emergency_service = db.Column(db.Boolean, default=False, nullable=False)
    accepts_insurance = db.Column(db.Boolean, default=False, nullable=False)
    
    # Operating Hours (stored as JSON or separate table)
    opening_time = db.Column(db.Time, default=time(8, 0), nullable=False)  # 8:00 AM
    closing_time = db.Column(db.Time, default=time(22, 0), nullable=False)  # 10:00 PM
    is_24_hours = db.Column(db.Boolean, default=False, nullable=False)
    
    # Rating and Reviews
    average_rating = db.Column(db.Numeric(3, 2), default=0.0, nullable=False)
    total_reviews = db.Column(db.Integer, default=0, nullable=False)
    
    # Relationships
    district = db.relationship('District', backref='pharmacies')
    products = db.relationship('Product', backref='pharmacy', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='pharmacy', lazy=True)
    
    def is_open_now(self):
        """Check if pharmacy is currently open"""
        if self.is_24_hours:
            return True
        
        now = datetime.now().time()
        return self.opening_time <= now <= self.closing_time
    
    def get_operating_hours_display(self):
        """Get formatted operating hours for display"""
        if self.is_24_hours:
            return "24 Hours"
        return f"{self.opening_time.strftime('%I:%M %p')} - {self.closing_time.strftime('%I:%M %p')}"
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary"""
        data = super().to_dict()
        data['status'] = self.status.value if self.status else None
        data['is_open_now'] = self.is_open_now()
        data['operating_hours'] = self.get_operating_hours_display()
        data['latitude'] = float(data['latitude']) if data['latitude'] else None
        data['longitude'] = float(data['longitude']) if data['longitude'] else None
        data['average_rating'] = float(data['average_rating']) if data['average_rating'] else 0.0
        
        if not include_sensitive:
            data.pop('license_number', None)
            data.pop('tax_number', None)
        
        return data
    
    def __repr__(self):
        return f'<Pharmacy {self.name}>'

class PharmacyDocument(BaseModel):
    __tablename__ = 'pharmacy_documents'
    
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    
    # Document Information
    document_type = db.Column(db.String(50), nullable=False)  # license, tax_certificate, etc.
    document_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    
    # Verification Status
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    verification_notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='documents')
    verifier = db.relationship('User', foreign_keys=[verified_by])
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        return data
    
    def __repr__(self):
        return f'<PharmacyDocument {self.document_type} for {self.pharmacy_id}>'
