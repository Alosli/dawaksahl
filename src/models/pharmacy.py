from src.models.database import db, BaseModel
import enum

class VerificationStatus(enum.Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class DocumentType(enum.Enum):
    LICENSE = 'license'
    BUSINESS_REGISTRATION = 'business_registration'
    TAX_CERTIFICATE = 'tax_certificate'
    OTHER = 'other'

class Pharmacy(BaseModel):
    __tablename__ = 'pharmacies'
    
    # Seller Reference
    seller_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Basic Information
    pharmacy_name = db.Column(db.String(200), nullable=False)
    pharmacy_name_ar = db.Column(db.String(200), nullable=True)
    license_number = db.Column(db.String(100), unique=True, nullable=True)
    description = db.Column(db.Text, nullable=True)
    description_ar = db.Column(db.Text, nullable=True)
    
    # Media
    logo_url = db.Column(db.Text, nullable=True)
    banner_url = db.Column(db.Text, nullable=True)
    
    # Contact Information
    phone_number = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    website_url = db.Column(db.Text, nullable=True)
    facebook_url = db.Column(db.Text, nullable=True)
    instagram_url = db.Column(db.Text, nullable=True)
    whatsapp_number = db.Column(db.String(20), nullable=True)
    
    # Location Information
    country = db.Column(db.String(100), default='Yemen', nullable=False)
    city = db.Column(db.String(100), default='Taiz', nullable=False)
    district = db.Column(db.String(100), nullable=False)
    detailed_address = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    
    # Status and Verification
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Rating System
    rating_average = db.Column(db.Numeric(3, 2), default=0.00, nullable=False)
    total_reviews = db.Column(db.Integer, default=0, nullable=False)
    
    # Relationships
    operating_hours = db.relationship('PharmacyOperatingHours', backref='pharmacy', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('PharmacyDocument', backref='pharmacy', lazy=True, cascade='all, delete-orphan')
    products = db.relationship('PharmacyProduct', backref='pharmacy', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='pharmacy', lazy=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['latitude'] = float(data['latitude']) if data['latitude'] else None
        data['longitude'] = float(data['longitude']) if data['longitude'] else None
        data['rating_average'] = float(data['rating_average']) if data['rating_average'] else 0.0
        return data
    
    def __repr__(self):
        return f'<Pharmacy {self.pharmacy_name}>'

class PharmacyOperatingHours(BaseModel):
    __tablename__ = 'pharmacy_operating_hours'
    
    pharmacy_id = db.Column(db.String(36), db.ForeignKey('pharmacies.id'), nullable=False)
    
    # Day and Time Information
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Sunday, 1=Monday, etc.
    opening_time = db.Column(db.Time, nullable=True)
    closing_time = db.Column(db.Time, nullable=True)
    is_closed = db.Column(db.Boolean, default=False, nullable=False)
    
    # Break Time (Optional)
    break_start_time = db.Column(db.Time, nullable=True)
    break_end_time = db.Column(db.Time, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['opening_time'] = data['opening_time'].strftime('%H:%M') if data['opening_time'] else None
        data['closing_time'] = data['closing_time'].strftime('%H:%M') if data['closing_time'] else None
        data['break_start_time'] = data['break_start_time'].strftime('%H:%M') if data['break_start_time'] else None
        data['break_end_time'] = data['break_end_time'].strftime('%H:%M') if data['break_end_time'] else None
        return data
    
    def __repr__(self):
        return f'<PharmacyOperatingHours {self.pharmacy_id} Day {self.day_of_week}>'

class PharmacyDocument(BaseModel):
    __tablename__ = 'pharmacy_documents'
    
    pharmacy_id = db.Column(db.String(36), db.ForeignKey('pharmacies.id'), nullable=False)
    
    # Document Information
    document_type = db.Column(db.Enum(DocumentType), nullable=False)
    document_url = db.Column(db.Text, nullable=False)
    document_name = db.Column(db.String(255), nullable=True)
    
    # Verification
    verification_status = db.Column(db.Enum(VerificationStatus), default=VerificationStatus.PENDING, nullable=False)
    admin_notes = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['document_type'] = self.document_type.value if self.document_type else None
        data['verification_status'] = self.verification_status.value if self.verification_status else None
        return data
    
    def __repr__(self):
        return f'<PharmacyDocument {self.document_type.value}>'

