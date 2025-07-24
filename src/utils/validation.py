import re
from typing import Dict, Any

# Regular expressions for validation
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PHONE_REGEX = re.compile(r'^(\+967|967|0)?[1-9]\d{7,8}$')  # Yemen phone number format
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,}$')

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))

def validate_phone(phone: str) -> bool:
    """Validate Yemen phone number format"""
    if not phone or not isinstance(phone, str):
        return False
    # Remove spaces and dashes
    clean_phone = re.sub(r'[\s-]', '', phone.strip())
    return bool(PHONE_REGEX.match(clean_phone))

def validate_password(password: str) -> Dict[str, Any]:
    """
    Validate password strength
    Returns dict with 'valid' boolean and 'message' string
    """
    if not password or not isinstance(password, str):
        return {'valid': False, 'message': 'Password is required'}
    
    if len(password) < 8:
        return {'valid': False, 'message': 'Password must be at least 8 characters long'}
    
    if len(password) > 128:
        return {'valid': False, 'message': 'Password must be less than 128 characters'}
    
    if not re.search(r'[a-z]', password):
        return {'valid': False, 'message': 'Password must contain at least one lowercase letter'}
    
    if not re.search(r'[A-Z]', password):
        return {'valid': False, 'message': 'Password must contain at least one uppercase letter'}
    
    if not re.search(r'\d', password):
        return {'valid': False, 'message': 'Password must contain at least one number'}
    
    # Check for common weak passwords
    weak_passwords = [
        'password', '12345678', 'qwerty123', 'admin123', 'user1234',
        'password123', '123456789', 'qwertyuiop', 'abc123456'
    ]
    
    if password.lower() in weak_passwords:
        return {'valid': False, 'message': 'Password is too common, please choose a stronger password'}
    
    return {'valid': True, 'message': 'Password is valid'}

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> Dict[str, Any]:
    """
    Validate that all required fields are present and not empty
    Returns dict with 'valid' boolean and 'message' string
    """
    if not isinstance(data, dict):
        return {'valid': False, 'message': 'Invalid data format'}
    
    missing_fields = []
    empty_fields = []
    
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif not data[field] or (isinstance(data[field], str) and not data[field].strip()):
            empty_fields.append(field)
    
    if missing_fields:
        return {'valid': False, 'message': f'Missing required fields: {", ".join(missing_fields)}'}
    
    if empty_fields:
        return {'valid': False, 'message': f'Empty required fields: {", ".join(empty_fields)}'}
    
    return {'valid': True, 'message': 'All required fields are valid'}

def validate_coordinates(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Validate geographic coordinates
    Returns dict with 'valid' boolean and 'message' string
    """
    try:
        lat = float(latitude)
        lng = float(longitude)
        
        if not (-90 <= lat <= 90):
            return {'valid': False, 'message': 'Latitude must be between -90 and 90'}
        
        if not (-180 <= lng <= 180):
            return {'valid': False, 'message': 'Longitude must be between -180 and 180'}
        
        # Check if coordinates are in Yemen (approximate bounds)
        # Yemen bounds: lat 12-19, lng 42-54
        if not (12 <= lat <= 19 and 42 <= lng <= 54):
            return {'valid': False, 'message': 'Coordinates must be within Yemen'}
        
        return {'valid': True, 'message': 'Coordinates are valid'}
        
    except (ValueError, TypeError):
        return {'valid': False, 'message': 'Invalid coordinate format'}

def validate_price(price: Any) -> Dict[str, Any]:
    """
    Validate price value
    Returns dict with 'valid' boolean and 'message' string
    """
    try:
        price_value = float(price)
        
        if price_value < 0:
            return {'valid': False, 'message': 'Price cannot be negative'}
        
        if price_value > 1000000:  # 1 million YER
            return {'valid': False, 'message': 'Price is too high'}
        
        # Check for reasonable decimal places (max 2)
        if len(str(price_value).split('.')[-1]) > 2:
            return {'valid': False, 'message': 'Price can have maximum 2 decimal places'}
        
        return {'valid': True, 'message': 'Price is valid'}
        
    except (ValueError, TypeError):
        return {'valid': False, 'message': 'Invalid price format'}

def validate_quantity(quantity: Any) -> Dict[str, Any]:
    """
    Validate quantity value
    Returns dict with 'valid' boolean and 'message' string
    """
    try:
        qty = int(quantity)
        
        if qty < 0:
            return {'valid': False, 'message': 'Quantity cannot be negative'}
        
        if qty > 10000:
            return {'valid': False, 'message': 'Quantity is too high'}
        
        return {'valid': True, 'message': 'Quantity is valid'}
        
    except (ValueError, TypeError):
        return {'valid': False, 'message': 'Invalid quantity format'}

def validate_file_upload(file, allowed_extensions=None, max_size=None):
    """
    Validate file upload
    Returns dict with 'valid' boolean and 'message' string
    """
    if not file:
        return {'valid': False, 'message': 'No file provided'}
    
    if not file.filename:
        return {'valid': False, 'message': 'No file selected'}
    
    # Check file extension
    if allowed_extensions:
        file_ext = file.filename.rsplit('.', 1)[-1].lower()
        if file_ext not in allowed_extensions:
            return {'valid': False, 'message': f'File type not allowed. Allowed types: {", ".join(allowed_extensions)}'}
    
    # Check file size
    if max_size:
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            return {'valid': False, 'message': f'File size too large. Maximum size: {max_size / (1024*1024):.1f}MB'}
    
    return {'valid': True, 'message': 'File is valid'}

def sanitize_string(value: str, max_length: int = None) -> str:
    """
    Sanitize string input by removing dangerous characters and trimming
    """
    if not isinstance(value, str):
        return str(value) if value is not None else ''
    
    # Remove null bytes and control characters
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Limit length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def validate_language_code(language: str) -> bool:
    """Validate language code (ar or en)"""
    return language in ['ar', 'en']

def validate_user_type(user_type: str) -> bool:
    """Validate user type"""
    return user_type in ['customer', 'seller', 'admin']

def validate_order_status(status: str) -> bool:
    """Validate order status"""
    valid_statuses = ['pending', 'confirmed', 'preparing', 'ready', 'delivered', 'cancelled']
    return status in valid_statuses

def validate_payment_method(method: str) -> bool:
    """Validate payment method"""
    valid_methods = ['cash_on_delivery', 'bank_transfer', 'mobile_payment']
    return method in valid_methods

