from src.models.database import db, BaseModel

class ProductCategory(BaseModel):
    __tablename__ = 'product_categories'
    
    # Category Information
    category_name = db.Column(db.String(200), nullable=False)
    category_name_ar = db.Column(db.String(200), nullable=True)
    parent_category_id = db.Column(db.String(36), db.ForeignKey('product_categories.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    description_ar = db.Column(db.Text, nullable=True)
    
    # Status and Ordering
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    
    # Relationships
    parent_category = db.relationship('ProductCategory', remote_side='ProductCategory.id', backref='subcategories')
    products = db.relationship('Product', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<ProductCategory {self.category_name}>'

class Product(BaseModel):
    __tablename__ = 'products'
    
    # Basic Product Information
    product_name = db.Column(db.String(300), nullable=False, index=True)
    product_name_ar = db.Column(db.String(300), nullable=True, index=True)
    generic_name = db.Column(db.String(300), nullable=True, index=True)
    generic_name_ar = db.Column(db.String(300), nullable=True, index=True)
    brand_name = db.Column(db.String(200), nullable=True, index=True)
    brand_name_ar = db.Column(db.String(200), nullable=True, index=True)
    
    # Category and Manufacturer
    category_id = db.Column(db.String(36), db.ForeignKey('product_categories.id'), nullable=True)
    manufacturer = db.Column(db.String(200), nullable=True)
    manufacturer_ar = db.Column(db.String(200), nullable=True)
    
    # Descriptions
    description = db.Column(db.Text, nullable=True)
    description_ar = db.Column(db.Text, nullable=True)
    
    # Medical Information
    dosage_form = db.Column(db.String(100), nullable=True)  # tablet, capsule, syrup, etc.
    strength = db.Column(db.String(100), nullable=True)  # 500mg, 10ml, etc.
    pack_size = db.Column(db.String(100), nullable=True)  # 30 tablets, 100ml bottle, etc.
    
    # Detailed Medical Information
    active_ingredients = db.Column(db.Text, nullable=True)
    active_ingredients_ar = db.Column(db.Text, nullable=True)
    contraindications = db.Column(db.Text, nullable=True)
    contraindications_ar = db.Column(db.Text, nullable=True)
    side_effects = db.Column(db.Text, nullable=True)
    side_effects_ar = db.Column(db.Text, nullable=True)
    storage_conditions = db.Column(db.Text, nullable=True)
    storage_conditions_ar = db.Column(db.Text, nullable=True)
    
    # Regulatory Information
    prescription_required = db.Column(db.Boolean, default=False, nullable=False)
    
    # Identification
    barcode = db.Column(db.String(100), nullable=True, unique=True)
    sku = db.Column(db.String(100), nullable=True, unique=True)
    
    # Media
    default_image_url = db.Column(db.Text, nullable=True)
    
    # Status and Metadata
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    creator = db.relationship('User', backref='created_products')
    pharmacy_products = db.relationship('PharmacyProduct', backref='product', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Product {self.product_name}>'

class PharmacyProduct(BaseModel):
    __tablename__ = 'pharmacy_products'
    
    # References
    pharmacy_id = db.Column(db.String(36), db.ForeignKey('pharmacies.id'), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    
    # Pricing and Inventory
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity_available = db.Column(db.Integer, default=0, nullable=False)
    minimum_quantity = db.Column(db.Integer, default=1, nullable=False)
    maximum_quantity = db.Column(db.Integer, nullable=True)
    
    # Pharmacy-specific Information
    custom_image_url = db.Column(db.Text, nullable=True)
    pharmacy_notes = db.Column(db.Text, nullable=True)
    pharmacy_notes_ar = db.Column(db.Text, nullable=True)
    
    # Availability
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    last_updated = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # Relationships
    cart_items = db.relationship('CartItem', backref='pharmacy_product', lazy=True, cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', backref='pharmacy_product', lazy=True)
    
    # Unique constraint to prevent duplicate products in same pharmacy
    __table_args__ = (db.UniqueConstraint('pharmacy_id', 'product_id', name='unique_pharmacy_product'),)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['price'] = float(data['price']) if data['price'] else 0.0
        return data
    
    def get_effective_image_url(self):
        """Get the image URL, preferring custom over default"""
        return self.custom_image_url or (self.product.default_image_url if self.product else None)
    
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.is_available and self.quantity_available > 0
    
    def can_order_quantity(self, quantity):
        """Check if a specific quantity can be ordered"""
        if not self.is_in_stock():
            return False
        if quantity < self.minimum_quantity:
            return False
        if self.maximum_quantity and quantity > self.maximum_quantity:
            return False
        return quantity <= self.quantity_available
    
    def __repr__(self):
        return f'<PharmacyProduct {self.pharmacy_id}:{self.product_id}>'

