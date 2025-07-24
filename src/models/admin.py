from src.models.database import db, BaseModel
import enum

class SettingType(enum.Enum):
    STRING = 'string'
    NUMBER = 'number'
    BOOLEAN = 'boolean'
    JSON = 'json'

class District(BaseModel):
    __tablename__ = 'districts'
    
    # District Information
    district_name = db.Column(db.String(100), nullable=False)
    district_name_ar = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), default='Taiz', nullable=False)
    country = db.Column(db.String(100), default='Yemen', nullable=False)
    
    # Geographic Information
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    # Status and Ordering
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['latitude'] = float(data['latitude']) if data['latitude'] else None
        data['longitude'] = float(data['longitude']) if data['longitude'] else None
        return data
    
    def __repr__(self):
        return f'<District {self.district_name}>'

class SystemSetting(BaseModel):
    __tablename__ = 'system_settings'
    
    # Setting Information
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    setting_type = db.Column(db.Enum(SettingType), default=SettingType.STRING, nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Visibility
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        data = super().to_dict()
        data['setting_type'] = self.setting_type.value if self.setting_type else None
        return data
    
    def get_typed_value(self):
        """Get value converted to appropriate type"""
        if self.setting_value is None:
            return None
        
        if self.setting_type == SettingType.BOOLEAN:
            return self.setting_value.lower() in ('true', '1', 'yes', 'on')
        elif self.setting_type == SettingType.NUMBER:
            try:
                if '.' in self.setting_value:
                    return float(self.setting_value)
                else:
                    return int(self.setting_value)
            except ValueError:
                return None
        elif self.setting_type == SettingType.JSON:
            try:
                import json
                return json.loads(self.setting_value)
            except (json.JSONDecodeError, TypeError):
                return None
        else:
            return self.setting_value
    
    def set_typed_value(self, value):
        """Set value from typed input"""
        if value is None:
            self.setting_value = None
        elif self.setting_type == SettingType.JSON:
            import json
            self.setting_value = json.dumps(value)
        else:
            self.setting_value = str(value)
    
    def __repr__(self):
        return f'<SystemSetting {self.setting_key}>'

class AuditLog(BaseModel):
    __tablename__ = 'audit_logs'
    
    # User and Action Information
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    action_type = db.Column(db.String(100), nullable=False, index=True)
    
    # Target Information
    table_name = db.Column(db.String(100), nullable=True, index=True)
    record_id = db.Column(db.String(36), nullable=True, index=True)
    
    # Change Information
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    
    # Request Information
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    user_agent = db.Column(db.Text, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.action_type} by {self.user_id}>'

# Initialize default districts for Taiz
def initialize_default_districts():
    """Initialize default districts for Taiz city"""
    default_districts = [
        {'district_name': 'Al-Qahirah', 'district_name_ar': 'القاهرة', 'sort_order': 1},
        {'district_name': 'Salh', 'district_name_ar': 'صالح', 'sort_order': 2},
        {'district_name': 'Al-Mudhaffar', 'district_name_ar': 'المظفر', 'sort_order': 3},
        {'district_name': 'Al-Tiziyah', 'district_name_ar': 'التعزية', 'sort_order': 4},
        {'district_name': 'Jabal Habashi', 'district_name_ar': 'جبل حبشي', 'sort_order': 5},
        {'district_name': 'Maqbanah', 'district_name_ar': 'مقبنة', 'sort_order': 6},
        {'district_name': 'Al-Silw', 'district_name_ar': 'السلو', 'sort_order': 7},
        {'district_name': 'Dimnat Khadir', 'district_name_ar': 'دمنة خدير', 'sort_order': 8},
        {'district_name': 'Al-Shamayatayn', 'district_name_ar': 'الشمايتين', 'sort_order': 9},
        {'district_name': 'Mawza', 'district_name_ar': 'الموزع', 'sort_order': 10},
        {'district_name': 'Al-Wazi\'iyah', 'district_name_ar': 'الوازعية', 'sort_order': 11},
        {'district_name': 'Hayfan', 'district_name_ar': 'حيفان', 'sort_order': 12},
        {'district_name': 'Mashra\'a wa Hadnan', 'district_name_ar': 'مشرعة وحدنان', 'sort_order': 13},
        {'district_name': 'Al-Ma\'afer', 'district_name_ar': 'المعافر', 'sort_order': 14},
        {'district_name': 'As Silw', 'district_name_ar': 'السلو', 'sort_order': 15},
        {'district_name': 'Sama', 'district_name_ar': 'سامع', 'sort_order': 16},
        {'district_name': 'Ash Shamayatayn', 'district_name_ar': 'الشمايتين', 'sort_order': 17},
        {'district_name': 'At Tiziyah', 'district_name_ar': 'التعزية', 'sort_order': 18},
        {'district_name': 'Harib', 'district_name_ar': 'حريب', 'sort_order': 19},
        {'district_name': 'Sabir al Mawadim', 'district_name_ar': 'صبر الموادم', 'sort_order': 20},
        {'district_name': 'Ash Sharab', 'district_name_ar': 'الشعب', 'sort_order': 21},
        {'district_name': 'Al Misrakh', 'district_name_ar': 'المسراخ', 'sort_order': 22},
        {'district_name': 'Al Mukha', 'district_name_ar': 'المخا', 'sort_order': 23}
    ]
    
    for district_data in default_districts:
        existing = District.query.filter_by(district_name=district_data['district_name']).first()
        if not existing:
            district = District(**district_data)
            db.session.add(district)
    
    db.session.commit()

# Initialize default system settings
def initialize_default_settings():
    """Initialize default system settings"""
    default_settings = [
        {
            'setting_key': 'site_name',
            'setting_value': 'DawakSahl',
            'setting_type': SettingType.STRING,
            'description': 'Website name',
            'is_public': True
        },
        {
            'setting_key': 'site_name_ar',
            'setting_value': 'دواك سهل',
            'setting_type': SettingType.STRING,
            'description': 'Website name in Arabic',
            'is_public': True
        },
        {
            'setting_key': 'default_language',
            'setting_value': 'ar',
            'setting_type': SettingType.STRING,
            'description': 'Default language for the platform',
            'is_public': True
        },
        {
            'setting_key': 'registration_enabled',
            'setting_value': 'true',
            'setting_type': SettingType.BOOLEAN,
            'description': 'Whether new user registration is enabled',
            'is_public': True
        },
        {
            'setting_key': 'pharmacy_verification_required',
            'setting_value': 'true',
            'setting_type': SettingType.BOOLEAN,
            'description': 'Whether pharmacy verification is required',
            'is_public': False
        },
        {
            'setting_key': 'max_file_upload_size',
            'setting_value': '16777216',
            'setting_type': SettingType.NUMBER,
            'description': 'Maximum file upload size in bytes',
            'is_public': False
        },
        {
            'setting_key': 'delivery_fee',
            'setting_value': '500',
            'setting_type': SettingType.NUMBER,
            'description': 'Default delivery fee in YER',
            'is_public': True
        },
        {
            'setting_key': 'tax_rate',
            'setting_value': '0.0',
            'setting_type': SettingType.NUMBER,
            'description': 'Tax rate as decimal (0.15 = 15%)',
            'is_public': True
        }
    ]
    
    for setting_data in default_settings:
        existing = SystemSetting.query.filter_by(setting_key=setting_data['setting_key']).first()
        if not existing:
            setting = SystemSetting(**setting_data)
            db.session.add(setting)
    
    db.session.commit()

