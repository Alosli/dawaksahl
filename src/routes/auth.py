from flask import Blueprint, request, jsonify
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
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name', 'user_type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'{field} is required'
                }), 400
        
        # Validate email format
        if not EMAIL_REGEX.match(data['email']):
            return jsonify({
                'success': False,
                'message': 'Invalid email format'
            }), 400
        
        # Check if user already exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({
                'success': False,
                'message': 'Email already registered'
            }), 409
        
        # Validate password
        password_validation = validate_password(data['password'])
        if not password_validation['valid']:
            return jsonify({
                'success': False,
                'message': password_validation['message']
            }), 400
        
        # Validate user type
        try:
            user_type = UserType(data['user_type'])
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid user type'
            }), 400
        
        # Validate phone if provided
        if 'phone' in data and data['phone']:
            phone_validation = validate_phone(data['phone'])
            if not phone_validation['valid']:
                return jsonify({
                    'success': False,
                    'message': phone_validation['message']
                }), 400
        
        # Create user
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            first_name_ar=data.get('first_name_ar'),
            last_name_ar=data.get('last_name_ar'),
            phone=data.get('phone'),
            user_type=user_type,
            preferred_language=data.get('preferred_language', 'en')
        )
        user.set_password(data['password'])
        user.generate_verification_token()
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create pharmacy if user is seller
        if user_type == UserType.SELLER:
            pharmacy_data = data.get('pharmacy', {})
            if not pharmacy_data:
                return jsonify({
                    'success': False,
                    'message': 'Pharmacy information is required for sellers'
                }), 400
            
            # Validate required pharmacy fields
            pharmacy_required = ['name', 'district_id', 'address', 'phone']
            for field in pharmacy_required:
                if field not in pharmacy_data or not pharmacy_data[field]:
                    return jsonify({
                        'success': False,
                        'message': f'Pharmacy {field} is required'
                    }), 400
            
            pharmacy = Pharmacy(
                seller_id=user.id,
                name=pharmacy_data['name'],
                name_ar=pharmacy_data.get('name_ar'),
                district_id=pharmacy_data['district_id'],
                address=pharmacy_data['address'],
                address_ar=pharmacy_data.get('address_ar'),
                phone=pharmacy_data['phone'],
                email=pharmacy_data.get('email'),
                description=pharmacy_data.get('description'),
                description_ar=pharmacy_data.get('description_ar'),
                latitude=pharmacy_data.get('latitude'),
                longitude=pharmacy_data.get('longitude')
            )
            db.session.add(pharmacy)
        
        # Create address if provided
        if 'address' in data and data['address']:
            address_data = data['address']
            address = UserAddress(
                user_id=user.id,
                label=address_data.get('label', 'Home'),
                address_line1=address_data['address_line1'],
                address_line2=address_data.get('address_line2'),
                district_id=address_data.get('district_id'),
                phone=address_data.get('phone'),
                is_default=True
            )
            db.session.add(address)
        
        db.session.commit()
        
        # Send verification email
        try:
            email_result = send_verification_email(
                user.email,
                user.get_full_name(),
                user.email_verification_token,
                user.preferred_language
            )
            if not email_result['success']:
                # Log email failure but don't fail registration
                print(f"Failed to send verification email: {email_result.get('error')}")
        except Exception as e:
            print(f"Error sending verification email: {str(e)}")
        
        # Log audit action
        log_audit_action(
            user.id,
            'create',
            'user',
            user.id,
            f"User registered with email {user.email}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Registration successful. Please check your email for verification.',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user_type': user.user_type.value,
                'email_verified': user.email_verified
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Registration failed: {str(e)}'
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({
                'success': False,
                'message': 'Email and password are required'
            }), 400
        
        # Find user
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({
                'success': False,
                'message': 'Invalid email or password'
            }), 401
        
        # Check if user is active
        if not user.is_active:
            return jsonify({
                'success': False,
                'message': 'Account is deactivated. Please contact support.'
            }), 403
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create tokens
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'user_type': user.user_type.value,
                'email_verified': user.email_verified
            }
        )
        refresh_token = create_refresh_token(identity=user.id)
        
        # Log audit action
        log_audit_action(
            user.id,
            'login',
            'user',
            user.id,
            f"User logged in from {request.remote_addr}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user_type': user.user_type.value,
                'email_verified': user.email_verified,
                'preferred_language': user.preferred_language
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login failed: {str(e)}'
        }), 500

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Email verification endpoint"""
    try:
        data = request.get_json()
        
        if not data or not data.get('token'):
            return jsonify({
                'success': False,
                'message': 'Verification token is required'
            }), 400
        
        # Find user by verification token
        user = User.query.filter_by(email_verification_token=data['token']).first()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired verification token'
            }), 400
        
        # Check if token is expired (24 hours)
        if user.email_verification_expires and user.email_verification_expires < datetime.utcnow():
            return jsonify({
                'success': False,
                'message': 'Verification token has expired. Please request a new one.'
            }), 400
        
        # Verify email
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_expires = None
        user.email_verified_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(
            user.id,
            'verify',
            'user',
            user.id,
            "Email verified successfully"
        )
        
        return jsonify({
            'success': True,
            'message': 'Email verified successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Email verification failed: {str(e)}'
        }), 500

@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend email verification"""
    try:
        data = request.get_json()
        
        if not data or not data.get('email'):
            return jsonify({
                'success': False,
                'message': 'Email is required'
            }), 400
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        if user.email_verified:
            return jsonify({
                'success': False,
                'message': 'Email is already verified'
            }), 400
        
        # Generate new verification token
        user.generate_verification_token()
        db.session.commit()
        
        # Send verification email
        try:
            email_result = send_verification_email(
                user.email,
                user.get_full_name(),
                user.email_verification_token,
                user.preferred_language
            )
            if not email_result['success']:
                return jsonify({
                    'success': False,
                    'message': 'Failed to send verification email'
                }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error sending verification email: {str(e)}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'Verification email sent successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to resend verification: {str(e)}'
        }), 500

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        
        if not data or not data.get('email'):
            return jsonify({
                'success': False,
                'message': 'Email is required'
            }), 400
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user:
            # Don't reveal if email exists or not
            return jsonify({
                'success': True,
                'message': 'If the email exists, a password reset link has been sent'
            })
        
        # Generate password reset token
        user.password_reset_token = secrets.token_urlsafe(32)
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        
        # Send password reset email
        try:
            email_result = send_password_reset_email(
                user.email,
                user.get_full_name(),
                user.password_reset_token,
                user.preferred_language
            )
            if not email_result['success']:
                print(f"Failed to send password reset email: {email_result.get('error')}")
        except Exception as e:
            print(f"Error sending password reset email: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'If the email exists, a password reset link has been sent'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to process password reset: {str(e)}'
        }), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        
        if not data or not data.get('token') or not data.get('password'):
            return jsonify({
                'success': False,
                'message': 'Token and new password are required'
            }), 400
        
        # Find user by reset token
        user = User.query.filter_by(password_reset_token=data['token']).first()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired reset token'
            }), 400
        
        # Check if token is expired
        if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
            return jsonify({
                'success': False,
                'message': 'Reset token has expired. Please request a new one.'
            }), 400
        
        # Validate new password
        password_validation = validate_password(data['password'])
        if not password_validation['valid']:
            return jsonify({
                'success': False,
                'message': password_validation['message']
            }), 400
        
        # Update password
        user.set_password(data['password'])
        user.password_reset_token = None
        user.password_reset_expires = None
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(
            user.id,
            'update',
            'user',
            user.id,
            "Password reset successfully"
        )
        
        return jsonify({
            'success': True,
            'message': 'Password reset successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Password reset failed: {str(e)}'
        }), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_active:
            return jsonify({
                'success': False,
                'message': 'User not found or inactive'
            }), 404
        
        # Create new access token
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'user_type': user.user_type.value,
                'email_verified': user.email_verified
            }
        )
        
        return jsonify({
            'success': True,
            'access_token': access_token
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Token refresh failed: {str(e)}'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (invalidate token)"""
    try:
        # In a production app, you'd want to blacklist the token
        # For now, we'll just return success
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Logout failed: {str(e)}'
        }), 500
