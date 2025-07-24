from .database import db, BaseModel
from datetime import datetime
import enum

class AuditAction(enum.Enum):
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    LOGIN = 'login'
    LOGOUT = 'logout'
    APPROVE = 'approve'
    REJECT = 'reject'
    SUSPEND = 'suspend'
    ACTIVATE = 'activate'

class District(BaseModel):
    __tablename__ = 'districts'
    
    # Basic Information
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=True)
    code = db.Column(db.String(10), unique=True, nullable=True)
    
    # Geographic Information
    governorate = db.Column(db.String(100), default='Taiz', nullable=False)
    governorate_ar = db.Column(db.String(100), default='تعز', nullable=False)
    
    # Coordinates (center point of district)
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    # Administrative Information
    population = db.Column(db.Integer, nullable=True)
    area_km2 = db.Column(db.Numeric(10, 2), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    delivery_available = db.Column(db.Boolean, default=True, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['latitude'] = float(data['latitude']) if data['latitude'] else None
        data['longitude'] = float(data['longitude']) if data['longitude'] else None
        data['area_km2'] = float(data['area_km2']) if data['area_km2'] else None
        data['pharmacy_count'] = len(self.pharmacies) if hasattr(self, 'pharmacies') else 0
        return data
    
    def __repr__(self):
        return f'<District {self.name}>'

class SystemSetting(BaseModel):
    __tablename__ = 'system_settings'
    
    # Setting Information
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    data_type = db.Column(db.String(20), default='string', nullable=False)  # string, integer, boolean, json
    
    # Metadata
    category = db.Column(db.String(50), nullable=False)  # general, payment, delivery, etc.
    description = db.Column(db.Text, nullable=True)
    description_ar = db.Column(db.Text, nullable=True)
    
    # Access Control
    is_public = db.Column(db.Boolean, default=False, nullable=False)  # Can be accessed by frontend
    is_editable = db.Column(db.Boolean, default=True, nullable=False)  # Can be modified
    
    def get_typed_value(self):
        """Get value converted to appropriate type"""
        if self.data_type == 'integer':
            return int(self.value) if self.value else 0
        elif self.data_type == 'boolean':
            return self.value.lower() in ['true', '1', 'yes'] if self.value else False
        elif self.data_type == 'json':
            import json
            return json.loads(self.value) if self.value else {}
        else:
            return self.value
    
    def set_typed_value(self, value):
        """Set value with type conversion"""
        if self.data_type == 'json':
            import json
            self.value = json.dumps(value)
        else:
            self.value = str(value)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['typed_value'] = self.get_typed_value()
        return data
    
    def __repr__(self):
        return f'<SystemSetting {self.key}>'

class AuditLog(BaseModel):
    __tablename__ = 'audit_logs'
    
    # User and Action Information
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.Enum(AuditAction), nullable=False)
    
    # Target Information
    target_type = db.Column(db.String(50), nullable=False)  # user, pharmacy, product, order, etc.
    target_id = db.Column(db.String(50), nullable=True)  # ID of the affected object
    
    # Details
    description = db.Column(db.Text, nullable=False)
    old_values = db.Column(db.Text, nullable=True)  # JSON string of old values
    new_values = db.Column(db.Text, nullable=True)  # JSON string of new values
    
    # Request Information
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    user_agent = db.Column(db.Text, nullable=True)
    request_method = db.Column(db.String(10), nullable=True)  # GET, POST, etc.
    request_url = db.Column(db.Text, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
    
    @classmethod
    def log_action(cls, user_id, action, target_type, target_id, description, 
                   old_values=None, new_values=None, ip_address=None, user_agent=None,
                   request_method=None, request_url=None):
        """Create an audit log entry"""
        import json
        
        log_entry = cls(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            description=description,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_url=request_url
        )
        
        db.session.add(log_entry)
        return log_entry
    
    def get_old_values_dict(self):
        """Get old values as dictionary"""
        if self.old_values:
            import json
            return json.loads(self.old_values)
        return {}
    
    def get_new_values_dict(self):
        """Get new values as dictionary"""
        if self.new_values:
            import json
            return json.loads(self.new_values)
        return {}
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['action'] = self.action.value if self.action else None
        data['old_values_dict'] = self.get_old_values_dict()
        data['new_values_dict'] = self.get_new_values_dict()
        return data
    
    def __repr__(self):
        return f'<AuditLog {self.action.value} on {self.target_type}:{self.target_id}>'

class Notification(BaseModel):
    __tablename__ = 'notifications'
    
    # Recipient Information
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Notification Content
    title = db.Column(db.String(255), nullable=False)
    title_ar = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=False)
    message_ar = db.Column(db.Text, nullable=True)
    
    # Notification Type and Priority
    notification_type = db.Column(db.String(50), nullable=False)  # order, pharmacy, system, etc.
    priority = db.Column(db.String(20), default='normal', nullable=False)  # low, normal, high, urgent
    
    # Status
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Related Object
    related_type = db.Column(db.String(50), nullable=True)  # order, pharmacy, etc.
    related_id = db.Column(db.String(50), nullable=True)
    
    # Action Information
    action_url = db.Column(db.String(500), nullable=True)
    action_text = db.Column(db.String(100), nullable=True)
    action_text_ar = db.Column(db.String(100), nullable=True)
    
    # Delivery Information
    sent_via_email = db.Column(db.Boolean, default=False, nullable=False)
    sent_via_sms = db.Column(db.Boolean, default=False, nullable=False)
    sent_via_push = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='notifications')
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    @classmethod
    def create_notification(cls, user_id, title, message, notification_type,
                          title_ar=None, message_ar=None, priority='normal',
                          related_type=None, related_id=None, action_url=None,
                          action_text=None, action_text_ar=None):
        """Create a new notification"""
        notification = cls(
            user_id=user_id,
            title=title,
            title_ar=title_ar,
            message=message,
            message_ar=message_ar,
            notification_type=notification_type,
            priority=priority,
            related_type=related_type,
            related_id=str(related_id) if related_id else None,
            action_url=action_url,
            action_text=action_text,
            action_text_ar=action_text_ar
        )
        
        db.session.add(notification)
        return notification
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        return data
    
    def __repr__(self):
        return f'<Notification {self.title} for User:{self.user_id}>'
