from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import secrets
import re

from src.models import db, User, UserAddress, UserType, Pharmacy, AuditLog
from src.utils.email import send_verification_email, send_password_reset_email
from src.utils.validation import validate_email, validate_password, validate_phone
from src.utils.auth import log_audit_action

auth_bp = Blueprint('auth', __name__)

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name', 'user_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate email format
        if not EMAIL_REGEX.match(data['email']):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password strength
        password_validation = validate_password(data['password'])
        if not password_validation['valid']:
            return jsonify({'error': password_validation['message']}), 400
        
        # Validate user type
        try:
            user_type = UserType(data['user_type'])
        except ValueError:
            return jsonify({'error': 'Invalid user type'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 409
        
        # Check phone number if provided
        if data.get('phone_number'):
            if not validate_phone(data['phone_number']):
                return jsonify({'error': 'Invalid phone number format'}), 400
            
            existing_phone = User.query.filter_by(phone_number=data['phone_number']).first()
            if existing_phone:
                return jsonify({'error': 'User with this phone number already exists'}), 409
        
        # Create user
        user = User(
            email=data['email'],
            phone_number=data.get('phone_number'),
            first_name=data['first_name'],
            last_name=data['last_name'],
            user_type=user_type,
            preferred_language=data.get('preferred_language', 'ar'),
            verification_token=secrets.token_urlsafe(32)
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create user address if provided
        if data.get('address'):
            address_data = data['address']
            address = UserAddress(
                user_id=user.id,
                country=address_data.get('country', 'Yemen'),
                city=address_data.get('city', 'Taiz'),
                district=address_data.get('district', ''),
                detailed_address=address_data.get('detailed_address'),
                latitude=address_data.get('latitude'),
                longitude=address_data.get('longitude'),
                is_primary=True
            )
            db.session.add(address)
        
        # Create pharmacy if user is seller
        if user_type == UserType.SELLER and data.get('pharmacy'):
            pharmacy_data = data['pharmacy']
            
            # Validate required pharmacy fields
            pharmacy_required = ['pharmacy_name', 'district', 'latitude', 'longitude']
            for field in pharmacy_required:
                if not pharmacy_data.get(field):
                    return jsonify({'error': f'Pharmacy {field} is required for sellers'}), 400
            
            pharmacy = Pharmacy(
                seller_id=user.id,
                pharmacy_name=pharmacy_data['pharmacy_name'],
                pharmacy_name_ar=pharmacy_data.get('pharmacy_name_ar'),
                description=pharmacy_data.get('description'),
                description_ar=pharmacy_data.get('description_ar'),
                phone_number=pharmacy_data.get('phone_number'),
                email=pharmacy_data.get('email'),
                country=pharmacy_data.get('country', 'Yemen'),
                city=pharmacy_data.get('city', 'Taiz'),
                district=pharmacy_data['district'],
                detailed_address=pharmacy_data.get('detailed_address'),
                latitude=pharmacy_data['latitude'],
                longitude=pharmacy_data['longitude']
            )
            db.session.add(pharmacy)
        
        db.session.commit()
        
        # Send verification email
        try:
            send_verification_email(user.email, user.full_name, user.verification_token, user.preferred_language)

        except Exception as e:
            current_app.logger.error(f"Failed to send verification email: {str(e)}")
        
        # Log audit action
        log_audit_action(user.id, 'user_registered', 'users', user.id, {}, user.to_dict())
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'verification_required': True
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find user by email or phone
        user = User.query.filter(
            (User.email == data['email']) | (User.phone_number == data['email'])
        ).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create tokens
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'user_type': user.user_type.value,
                'is_verified': user.is_verified
            }
        )
        refresh_token = create_refresh_token(identity=user.id)
        
        # Log audit action
        log_audit_action(user.id, 'user_login', 'users', user.id, {}, {'last_login': user.last_login.isoformat()})
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 404
        
        # Create new access token
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'user_type': user.user_type.value,
                'is_verified': user.is_verified
            }
        )
        
        return jsonify({
            'access_token': access_token
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Token refresh failed'}), 500

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Email verification endpoint"""
    try:
        data = request.get_json()
        
        if not data.get('token'):
            return jsonify({'error': 'Verification token is required'}), 400
        
        user = User.query.filter_by(verification_token=data['token']).first()
        if not user:
            return jsonify({'error': 'Invalid verification token'}), 400
        
        if user.is_verified:
            return jsonify({'message': 'Email already verified'}), 200
        
        # Verify user
        user.is_verified = True
        user.verification_token = None
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'email_verified', 'users', user.id, {'is_verified': False}, {'is_verified': True})
        
        return jsonify({
            'message': 'Email verified successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Email verification error: {str(e)}")
        return jsonify({'error': 'Email verification failed'}), 500

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Forgot password endpoint"""
    try:
        data = request.get_json()
        
        if not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400
        
        user = User.query.filter_by(email=data['email']).first()
        if not user:
            # Don't reveal if email exists
            return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        user.verification_token = reset_token  # Reuse verification_token field
        db.session.commit()
        
        # Send reset email
        try:
            send_password_reset_email(user.email, reset_token, user.preferred_language)
        except Exception as e:
            current_app.logger.error(f"Failed to send password reset email: {str(e)}")
        
        # Log audit action
        log_audit_action(user.id, 'password_reset_requested', 'users', user.id, {}, {})
        
        return jsonify({
            'message': 'If the email exists, a reset link has been sent'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Forgot password error: {str(e)}")
        return jsonify({'error': 'Password reset request failed'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password endpoint"""
    try:
        data = request.get_json()
        
        if not data.get('token') or not data.get('password'):
            return jsonify({'error': 'Token and new password are required'}), 400
        
        # Validate password strength
        password_validation = validate_password(data['password'])
        if not password_validation['valid']:
            return jsonify({'error': password_validation['message']}), 400
        
        user = User.query.filter_by(verification_token=data['token']).first()
        if not user:
            return jsonify({'error': 'Invalid reset token'}), 400
        
        # Reset password
        user.set_password(data['password'])
        user.verification_token = None
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'password_reset', 'users', user.id, {}, {})
        
        return jsonify({
            'message': 'Password reset successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password reset error: {str(e)}")
        return jsonify({'error': 'Password reset failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout endpoint (for audit logging)"""
    try:
        current_user_id = get_jwt_identity()
        
        # Log audit action
        log_audit_action(current_user_id, 'user_logout', 'users', current_user_id, {}, {})
        
        return jsonify({
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user information"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get current user error: {str(e)}")
        return jsonify({'error': 'Failed to get user information'}), 500
