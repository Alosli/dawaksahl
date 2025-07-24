from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime
import ipaddress

from src.models import db, User, AuditLog, UserType

def require_user_type(*allowed_types):
    """
    Decorator to require specific user types
    Usage: @require_user_type(UserType.ADMIN, UserType.SELLER)
    """
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if not user.is_active:
                return jsonify({'error': 'Account is deactivated'}), 403
            
            if user.user_type not in allowed_types:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_verified_user(f):
    """Decorator to require verified users"""
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_verified:
            return jsonify({'error': 'Email verification required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """Decorator to require admin user"""
    return require_user_type(UserType.ADMIN)(f)

def require_seller(f):
    """Decorator to require seller user"""
    return require_user_type(UserType.SELLER)(f)

def require_customer(f):
    """Decorator to require customer user"""
    return require_user_type(UserType.CUSTOMER)(f)

def require_seller_or_admin(f):
    """Decorator to require seller or admin user"""
    return require_user_type(UserType.SELLER, UserType.ADMIN)(f)

def get_current_user():
    """Get current authenticated user"""
    try:
        current_user_id = get_jwt_identity()
        if current_user_id:
            return User.query.get(current_user_id)
    except:
        pass
    return None

def get_client_ip():
    """Get client IP address from request"""
    # Check for forwarded IP first (for proxy/load balancer scenarios)
    if request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr
    
    # Validate IP address
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return request.remote_addr

def get_user_agent():
    """Get user agent from request"""
    return request.headers.get('User-Agent', '')

def log_audit_action(user_id, action_type, table_name=None, record_id=None, old_values=None, new_values=None):
    """
    Log audit action to database
    
    Args:
        user_id: ID of user performing action
        action_type: Type of action (e.g., 'user_login', 'product_created')
        table_name: Name of affected table
        record_id: ID of affected record
        old_values: Previous values (for updates)
        new_values: New values (for creates/updates)
    """
    try:
        audit_log = AuditLog(
            user_id=user_id,
            action_type=action_type,
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=get_client_ip(),
            user_agent=get_user_agent()
        )
        
        db.session.add(audit_log)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Failed to log audit action: {str(e)}")
        db.session.rollback()

def check_rate_limit(user_id, action_type, max_attempts=5, time_window=300):
    """
    Check if user has exceeded rate limit for specific action
    
    Args:
        user_id: User ID
        action_type: Type of action to check
        max_attempts: Maximum attempts allowed
        time_window: Time window in seconds
    
    Returns:
        bool: True if within rate limit, False if exceeded
    """
    try:
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(seconds=time_window)
        
        recent_attempts = AuditLog.query.filter(
            AuditLog.user_id == user_id,
            AuditLog.action_type == action_type,
            AuditLog.created_at >= cutoff_time
        ).count()
        
        return recent_attempts < max_attempts
        
    except Exception as e:
        current_app.logger.error(f"Rate limit check failed: {str(e)}")
        return True  # Allow action if check fails

def is_pharmacy_owner(user_id, pharmacy_id):
    """Check if user owns the specified pharmacy"""
    try:
        from src.models import Pharmacy
        pharmacy = Pharmacy.query.filter_by(id=pharmacy_id, seller_id=user_id).first()
        return pharmacy is not None
    except:
        return False

def can_access_pharmacy(user, pharmacy_id):
    """Check if user can access pharmacy data"""
    if not user:
        return False
    
    # Admin can access all pharmacies
    if user.user_type == UserType.ADMIN:
        return True
    
    # Seller can only access their own pharmacy
    if user.user_type == UserType.SELLER:
        return is_pharmacy_owner(user.id, pharmacy_id)
    
    return False

def can_access_order(user, order):
    """Check if user can access order data"""
    if not user or not order:
        return False
    
    # Admin can access all orders
    if user.user_type == UserType.ADMIN:
        return True
    
    # Customer can access their own orders
    if user.user_type == UserType.CUSTOMER and order.user_id == user.id:
        return True
    
    # Seller can access orders for their pharmacy
    if user.user_type == UserType.SELLER and order.pharmacy_id == user.pharmacy.id:
        return True
    
    return False

def generate_api_response(data=None, message=None, error=None, status_code=200):
    """
    Generate standardized API response
    
    Args:
        data: Response data
        message: Success message
        error: Error message
        status_code: HTTP status code
    
    Returns:
        tuple: (response_dict, status_code)
    """
    response = {
        'success': status_code < 400,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    if error:
        response['error'] = error
    
    return response, status_code

def validate_pagination_params(page=1, per_page=20, max_per_page=100):
    """
    Validate and sanitize pagination parameters
    
    Args:
        page: Page number
        per_page: Items per page
        max_per_page: Maximum items per page
    
    Returns:
        tuple: (page, per_page)
    """
    try:
        page = max(1, int(page))
    except (ValueError, TypeError):
        page = 1
    
    try:
        per_page = max(1, min(int(per_page), max_per_page))
    except (ValueError, TypeError):
        per_page = 20
    
    return page, per_page

def format_search_query(query):
    """
    Format search query for database search
    
    Args:
        query: Search query string
    
    Returns:
        str: Formatted query for LIKE operations
    """
    if not query or not isinstance(query, str):
        return ''
    
    # Remove special characters and extra spaces
    import re
    cleaned = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', query)  # Keep Arabic characters
    cleaned = ' '.join(cleaned.split())  # Remove extra spaces
    
    # Add wildcards for LIKE search
    return f'%{cleaned}%'

def hash_sensitive_data(data):
    """
    Hash sensitive data for logging (one-way hash)
    
    Args:
        data: Sensitive data to hash
    
    Returns:
        str: Hashed data
    """
    import hashlib
    if not data:
        return None
    
    return hashlib.sha256(str(data).encode()).hexdigest()[:16]  # First 16 chars

