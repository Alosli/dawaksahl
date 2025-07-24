from .database import db, BaseModel
from datetime import datetime
import enum

class OrderStatus(enum.Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    PROCESSING = 'processing'
    READY_FOR_PICKUP = 'ready_for_pickup'
    OUT_FOR_DELIVERY = 'out_for_delivery'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

class PaymentStatus(enum.Enum):
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class PaymentMethod(enum.Enum):
    CASH_ON_DELIVERY = 'cash_on_delivery'
    BANK_TRANSFER = 'bank_transfer'
    MOBILE_PAYMENT = 'mobile_payment'
    CREDIT_CARD = 'credit_card'

class DeliveryMethod(enum.Enum):
    PICKUP = 'pickup'
    STANDARD_DELIVERY = 'standard_delivery'
    EXPRESS_DELIVERY = 'express_delivery'
    SAME_DAY_DELIVERY = 'same_day_delivery'

class Order(BaseModel):
    __tablename__ = 'orders'
    
    # Order Identification
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    
    # Customer and Pharmacy
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    
    # Order Status
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    
    # Pricing Information
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0, nullable=False)
    delivery_fee = db.Column(db.Numeric(10, 2), default=0.0, nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.0, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='YER', nullable=False)
    
    # Payment Information
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    
    # Delivery Information
    delivery_method = db.Column(db.Enum(DeliveryMethod), default=DeliveryMethod.PICKUP, nullable=False)
    delivery_address = db.Column(db.Text, nullable=True)
    delivery_phone = db.Column(db.String(20), nullable=True)
    delivery_notes = db.Column(db.Text, nullable=True)
    
    # Timing
    estimated_delivery_date = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    
    # Additional Information
    prescription_required = db.Column(db.Boolean, default=False, nullable=False)
    prescription_uploaded = db.Column(db.Boolean, default=False, nullable=False)
    prescription_file_path = db.Column(db.String(500), nullable=True)
    
    special_instructions = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def generate_order_number(self):
        """Generate unique order number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"DWK{timestamp}"
    
    def calculate_totals(self):
        """Calculate order totals from items"""
        self.subtotal = sum(item.total_price for item in self.items)
        self.total_amount = self.subtotal + self.tax_amount + self.delivery_fee - self.discount_amount
    
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['status'] = self.status.value if self.status else None
        data['payment_status'] = self.payment_status.value if self.payment_status else None
        data['payment_method'] = self.payment_method.value if self.payment_method else None
        data['delivery_method'] = self.delivery_method.value if self.delivery_method else None
        data['subtotal'] = float(data['subtotal']) if data['subtotal'] else 0.0
        data['tax_amount'] = float(data['tax_amount']) if data['tax_amount'] else 0.0
        data['delivery_fee'] = float(data['delivery_fee']) if data['delivery_fee'] else 0.0
        data['discount_amount'] = float(data['discount_amount']) if data['discount_amount'] else 0.0
        data['total_amount'] = float(data['total_amount']) if data['total_amount'] else 0.0
        data['can_be_cancelled'] = self.can_be_cancelled()
        return data
    
    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(BaseModel):
    __tablename__ = 'order_items'
    
    # References
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Product Information (snapshot at time of order)
    product_name = db.Column(db.String(255), nullable=False)
    product_name_ar = db.Column(db.String(255), nullable=True)
    product_sku = db.Column(db.String(100), nullable=True)
    
    # Pricing and Quantity
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='YER', nullable=False)
    
    # Product Details (snapshot)
    requires_prescription = db.Column(db.Boolean, default=False, nullable=False)
    dosage = db.Column(db.String(100), nullable=True)
    pack_size = db.Column(db.String(100), nullable=True)
    
    def calculate_total(self):
        """Calculate total price for this item"""
        self.total_price = self.quantity * self.unit_price
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['unit_price'] = float(data['unit_price']) if data['unit_price'] else 0.0
        data['total_price'] = float(data['total_price']) if data['total_price'] else 0.0
        return data
    
    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'

class ShoppingCart(BaseModel):
    __tablename__ = 'shopping_carts'
    
    # User Reference
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Cart Information
    total_items = db.Column(db.Integer, default=0, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), default=0.0, nullable=False)
    currency = db.Column(db.String(3), default='YER', nullable=False)
    
    # Session Information
    session_id = db.Column(db.String(100), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    items = db.relationship('CartItem', backref='cart', lazy=True, cascade='all, delete-orphan')
    
    def calculate_totals(self):
        """Calculate cart totals from items"""
        self.total_items = sum(item.quantity for item in self.items)
        self.total_amount = sum(item.total_price for item in self.items)
    
    def add_item(self, product, quantity=1):
        """Add item to cart or update quantity if exists"""
        existing_item = CartItem.query.filter_by(
            cart_id=self.id,
            product_id=product.id
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.calculate_total()
        else:
            new_item = CartItem(
                cart_id=self.id,
                product_id=product.id,
                product_name=product.name,
                product_name_ar=product.name_ar,
                quantity=quantity,
                unit_price=product.price,
                pharmacy_id=product.pharmacy_id
            )
            new_item.calculate_total()
            db.session.add(new_item)
        
        self.calculate_totals()
    
    def remove_item(self, product_id):
        """Remove item from cart"""
        item = CartItem.query.filter_by(
            cart_id=self.id,
            product_id=product_id
        ).first()
        
        if item:
            db.session.delete(item)
            self.calculate_totals()
    
    def clear(self):
        """Clear all items from cart"""
        CartItem.query.filter_by(cart_id=self.id).delete()
        self.total_items = 0
        self.total_amount = 0.0
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['total_amount'] = float(data['total_amount']) if data['total_amount'] else 0.0
        return data
    
    def __repr__(self):
        return f'<ShoppingCart User:{self.user_id} Items:{self.total_items}>'

class CartItem(BaseModel):
    __tablename__ = 'cart_items'
    
    # References
    cart_id = db.Column(db.Integer, db.ForeignKey('shopping_carts.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    
    # Product Information (snapshot)
    product_name = db.Column(db.String(255), nullable=False)
    product_name_ar = db.Column(db.String(255), nullable=True)
    
    # Pricing and Quantity
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='YER', nullable=False)
    
    # Relationships
    pharmacy = db.relationship('Pharmacy', backref='cart_items')
    
    def calculate_total(self):
        """Calculate total price for this item"""
        self.total_price = self.quantity * self.unit_price
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['unit_price'] = float(data['unit_price']) if data['unit_price'] else 0.0
        data['total_price'] = float(data['total_price']) if data['total_price'] else 0.0
        return data
    
    def __repr__(self):
        return f'<CartItem {self.product_name} x{self.quantity}>'
