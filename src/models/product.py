from .database import db, BaseModel
from datetime import datetime
import enum

class ProductStatus(enum.Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    OUT_OF_STOCK = 'out_of_stock'
    DISCONTINUED = 'discontinued'

class Product(BaseModel):
    __tablename__ = 'products'
    
    # Basic Information
    name = db.Column(db.String(255), nullable=False)
    name_ar = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    description_ar = db.Column(db.Text, nullable=True)
    
    # Product Details
    brand = db.Column(db.String(100), nullable=True)
    manufacturer = db.Column(db.String(200), nullable=True)
    barcode = db.Column(db.String(50), unique=True, nullable=True)
    sku = db.Column(db.String(100), nullable=True)
    
    # Categorization
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.id'), nullable=False)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    
    # Pricing
    price = db.Column(db.Numeric(10, 2), nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=True)  # For pharmacy's cost tracking
    original_price = db.Column(db.Numeric(10, 2), nullable=True)  # For showing discounts
    currency = db.Column(db.String(3), default='YER', nullable=False)
    
    # Inventory
    quantity_in_stock = db.Column(db.Integer, default=0, nullable=False)
    minimum_stock_level = db.Column(db.Integer, default=5, nullable=False)
    maximum_stock_level = db.Column(db.Integer, default=100, nullable=False)
    
    # Product Specifications
    dosage = db.Column(db.String(100), nullable=True)  # e.g., "500mg"
    pack_size = db.Column(db.String(100), nullable=True)  # e.g., "20 tablets"
    expiry_date = db.Column(db.Date, nullable=True)
    batch_number = db.Column(db.String(50), nullable=True)
    
    # Regulatory Information
    requires_prescription = db.Column(db.Boolean, default=False, nullable=False)
    controlled_substance = db.Column(db.Boolean, default=False, nullable=False)
    age_restriction = db.Column(db.Integer, nullable=True)  # Minimum age required
    
    # Status and Visibility
    status = db.Column(db.Enum(ProductStatus), default=ProductStatus.ACTIVE, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_available_online = db.Column(db.Boolean, default=True, nullable=False)
    
    # SEO and Marketing
    meta_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.Text, nullable=True)
    keywords = db.Column(db.Text, nullable=True)  # Comma-separated keywords
    
    # Images and Media
    primary_image_url = db.Column(db.String(500), nullable=True)
    image_urls = db.Column(db.Text, nullable=True)  # JSON array of image URLs
    
    # Rating and Reviews
    average_rating = db.Column(db.Numeric(3, 2), default=0.0, nullable=False)
    total_reviews = db.Column(db.Integer, default=0, nullable=False)
    total_sales = db.Column(db.Integer, default=0, nullable=False)
    
    # Relationships
    category = db.relationship('ProductCategory', backref='products')
    cart_items = db.relationship('CartItem', backref='product', lazy=True, cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.quantity_in_stock > 0 and self.status == ProductStatus.ACTIVE
    
    @property
    def is_low_stock(self):
        """Check if product is low in stock"""
        return self.quantity_in_stock <= self.minimum_stock_level
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.cost_price and self.cost_price > 0:
            return ((self.price - self.cost_price) / self.cost_price) * 100
        return 0
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage if original price exists"""
        if self.original_price and self.original_price > self.price:
            return ((self.original_price - self.price) / self.original_price) * 100
        return 0
    
    def update_stock(self, quantity_change):
        """Update stock quantity"""
        new_quantity = self.quantity_in_stock + quantity_change
        if new_quantity < 0:
            raise ValueError("Insufficient stock")
        
        self.quantity_in_stock = new_quantity
        
        # Auto-update status based on stock
        if new_quantity == 0:
            self.status = ProductStatus.OUT_OF_STOCK
        elif self.status == ProductStatus.OUT_OF_STOCK and new_quantity > 0:
            self.status = ProductStatus.ACTIVE
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary"""
        data = super().to_dict()
        data['status'] = self.status.value if self.status else None
        data['is_in_stock'] = self.is_in_stock
        data['is_low_stock'] = self.is_low_stock
        data['profit_margin'] = float(self.profit_margin)
        data['discount_percentage'] = float(self.discount_percentage)
        data['price'] = float(data['price']) if data['price'] else 0.0
        data['cost_price'] = float(data['cost_price']) if data['cost_price'] else None
        data['original_price'] = float(data['original_price']) if data['original_price'] else None
        data['average_rating'] = float(data['average_rating']) if data['average_rating'] else 0.0
        
        if not include_sensitive:
            data.pop('cost_price', None)
        
        return data
    
    def __repr__(self):
        return f'<Product {self.name}>'

class ProductCategory(BaseModel):
    __tablename__ = 'product_categories'
    
    # Basic Information
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    description_ar = db.Column(db.Text, nullable=True)
    
    # Hierarchy
    parent_id = db.Column(db.Integer, db.ForeignKey('product_categories.id'), nullable=True)
    
    # Display Information
    icon = db.Column(db.String(100), nullable=True)  # Icon class or URL
    color = db.Column(db.String(7), nullable=True)  # Hex color code
    image_url = db.Column(db.String(500), nullable=True)
    
    # SEO and Organization
    slug = db.Column(db.String(100), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    parent = db.relationship('ProductCategory', remote_side='ProductCategory.id', backref='children')
    
    def get_full_path(self):
        """Get full category path"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['full_path'] = self.get_full_path()
        data['product_count'] = len(self.products)
        return data
    
    def __repr__(self):
        return f'<ProductCategory {self.name}>'
        
class PharmacyProduct(BaseModel):
    __tablename__ = 'pharmacy_products'

    pharmacy_id        = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    product_id         = db.Column(db.Integer, db.ForeignKey('products.id'),   nullable=False)
    price              = db.Column(db.Numeric(10, 2), nullable=False)
    quantity_available = db.Column(db.Integer,         nullable=False)
    minimum_quantity   = db.Column(db.Integer,         nullable=True)
    maximum_quantity   = db.Column(db.Integer,         nullable=True)
    custom_image_url   = db.Column(db.String(500),     nullable=True)
    pharmacy_notes     = db.Column(db.Text,            nullable=True)
    pharmacy_notes_ar  = db.Column(db.Text,            nullable=True)
    is_available       = db.Column(db.Boolean, default=True, nullable=False)

    product  = db.relationship('Product', backref='pharmacy_products')

    def to_dict(self):
        data       = super().to_dict()
        data['price'] = float(data['price']) if data['price'] else 0.0
        return data

    def __repr__(self):
        return f'<PharmacyProduct {self.pharmacy_id}-{self.product_id}>'

