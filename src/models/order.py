from src.models.database import db, BaseModel
from datetime import datetime
import enum
import secrets
import string

class OrderStatus(enum.Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    PREPARING = 'preparing'
    READY = 'ready'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

class PaymentMethod(enum.Enum):
    CASH_ON_DELIVERY = 'cash_on_delivery'
    BANK_TRANSFER = 'bank_transfer'
    MOBILE_PAYMENT = 'mobile_payment'

class PaymentStatus(enum.Enum):
    PENDING = 'pending'
    PAID = 'paid'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class ShoppingCart(BaseModel):
    __tablename__ = 'shopping_carts'
    
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Relationships
    items = db.relationship('CartItem', backref='cart', lazy=True, cascade='all, delete-orphan')
    
    def get_total_items(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items)
    
    def get_total_amount(self):
        """Get total amount for all items in cart"""
        return sum(item.get_total_price() for item in self.items)
    
    def get_items_by_pharmacy(self):
        """Group cart items by pharmacy"""
        pharmacy_groups = {}
        for item in self.items:
            pharmacy_id = item.pharmacy_product.pharmacy_id
            if pharmacy_id not in pharmacy_groups:
                pharmacy_groups[pharmacy_id] = []
            pharmacy_groups[pharmacy_id].append(item)
        return pharmacy_groups
    
    def clear(self):
        """Remove all items from cart"""
        for item in self.items:
            db.session.delete(item)
    
    def __repr__(self):
        return f'<ShoppingCart {self.user_id}>'

class CartItem(BaseModel):
    __tablename__ = 'cart_items'
    
    cart_id = db.Column(db.String(36), db.ForeignKey('shopping_carts.id'), nullable=False)
    pharmacy_product_id = db.Column(db.String(36), db.ForeignKey('pharmacy_products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    
    # Unique constraint to prevent duplicate items in same cart
    __table_args__ = (db.UniqueConstraint('cart_id', 'pharmacy_product_id', name='unique_cart_item'),)
    
    def get_total_price(self):
        """Get total price for this cart item"""
        return float(self.pharmacy_product.price) * self.quantity
    
    def can_increase_quantity(self, amount=1):
        """Check if quantity can be increased"""
        new_quantity = self.quantity + amount
        return self.pharmacy_product.can_order_quantity(new_quantity)
    
    def __repr__(self):
        return f'<CartItem {self.cart_id}:{self.pharmacy_product_id}>'

def generate_order_number():
    """Generate unique order number"""
    timestamp = datetime.now().strftime('%Y%m%d')
    random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f'DS{timestamp}{random_part}'

class Order(BaseModel):
    __tablename__ = 'orders'
    
    # References
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    pharmacy_id = db.Column(db.String(36), db.ForeignKey('pharmacies.id'), nullable=False)
    
    # Order Information
    order_number = db.Column(db.String(50), unique=True, nullable=False, default=generate_order_number)
    order_status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    
    # Financial Information
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    delivery_fee = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    
    # Payment Information
    payment_method = db.Column(db.Enum(PaymentMethod), default=PaymentMethod.CASH_ON_DELIVERY, nullable=False)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Delivery Information
    delivery_address = db.Column(db.Text, nullable=False)
    delivery_latitude = db.Column(db.Numeric(10, 8), nullable=True)
    delivery_longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    # Notes and Communication
    customer_notes = db.Column(db.Text, nullable=True)
    pharmacy_notes = db.Column(db.Text, nullable=True)
    
    # Timing
    estimated_delivery_time = db.Column(db.DateTime, nullable=True)
    actual_delivery_time = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['order_status'] = self.order_status.value if self.order_status else None
        data['payment_method'] = self.payment_method.value if self.payment_method else None
        data['payment_status'] = self.payment_status.value if self.payment_status else None
        data['total_amount'] = float(data['total_amount']) if data['total_amount'] else 0.0
        data['delivery_fee'] = float(data['delivery_fee']) if data['delivery_fee'] else 0.0
        data['tax_amount'] = float(data['tax_amount']) if data['tax_amount'] else 0.0
        data['discount_amount'] = float(data['discount_amount']) if data['discount_amount'] else 0.0
        data['delivery_latitude'] = float(data['delivery_latitude']) if data['delivery_latitude'] else None
        data['delivery_longitude'] = float(data['delivery_longitude']) if data['delivery_longitude'] else None
        return data
    
    def get_total_items(self):
        """Get total number of items in order"""
        return sum(item.quantity for item in self.items)
    
    def get_subtotal(self):
        """Get subtotal (before fees and taxes)"""
        return sum(item.total_price for item in self.items)
    
    def get_final_total(self):
        """Get final total including all fees and discounts"""
        subtotal = self.get_subtotal()
        return subtotal + float(self.delivery_fee) + float(self.tax_amount) - float(self.discount_amount)
    
    def can_cancel(self):
        """Check if order can be cancelled"""
        return self.order_status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]
    
    def can_update_status(self, new_status):
        """Check if order status can be updated to new status"""
        status_transitions = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
            OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
            OrderStatus.READY: [OrderStatus.DELIVERED],
            OrderStatus.DELIVERED: [],
            OrderStatus.CANCELLED: []
        }
        return new_status in status_transitions.get(self.order_status, [])
    
    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(BaseModel):
    __tablename__ = 'order_items'
    
    # References
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'), nullable=False)
    pharmacy_product_id = db.Column(db.String(36), db.ForeignKey('pharmacy_products.id'), nullable=False)
    
    # Product Information (snapshot at time of order)
    product_name = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['unit_price'] = float(data['unit_price']) if data['unit_price'] else 0.0
        data['total_price'] = float(data['total_price']) if data['total_price'] else 0.0
        return data
    
    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'

