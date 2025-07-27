from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import secrets

from src.models import db, User, UserAddress, Pharmacy, UserType
from src.utils.validation import validate_email, validate_password, validate_phone
from src.utils.auth import log_audit_action
from src.utils.email import send_verification_email, send_password_reset_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
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
        
        # Validate email
        email_validation = validate_email(data['email'])
        if not validate_email(data['email']):  # ✅ Direct boolean check
            return jsonify({'success': False, 'message': 'Invalid email format'}), 400
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
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
        
        # Validate phone if provided
        if 'phone_number' in data and data['phone_number']:
            phone_validation = validate_phone(data['phone_number'])
            if not validate_phone(data['phone_number']):
                return jsonify({'success': False, 'message': 'Invalid phone number format'}), 400
            
            # Check if phone already exists
            existing_phone = User.query.filter_by(phone_number=data['phone_number']).first()
            if existing_phone:
                return jsonify({
                    'success': False,
                    'message': 'Phone number already registered'
                }), 409
        
        # Validate user type
        try:
            user_type = UserType(data['user_type'])
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid user type'
            }), 400
        
        # Create user
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone_number=data.get('phone_number'),
            user_type=user_type,
            preferred_language=data.get('preferred_language', 'ar')
        )
        user.set_password(data['password'])
        user.generate_verification_token()
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create pharmacy for sellers
        if user_type == UserType.SELLER:
            pharmacy_data = data.get('pharmacy')
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
                description=pharmacy_data.get('description'),
                description_ar=pharmacy_data.get('description_ar'),
                phone=pharmacy_data['phone'],
                email=pharmacy_data.get('email'),
                website=pharmacy_data.get('website'),
                address=pharmacy_data['address'],
                district_id=pharmacy_data['district_id'],
                latitude=pharmacy_data.get('latitude'),
                longitude=pharmacy_data.get('longitude'),
                license_number=pharmacy_data.get('license_number'),
                tax_number=pharmacy_data.get('tax_number'),
                delivery_available=pharmacy_data.get('delivery_available', False),
                emergency_service=pharmacy_data.get('emergency_service', False),
                accepts_insurance=pharmacy_data.get('accepts_insurance', False),
                opening_time=pharmacy_data.get('opening_time'),
                closing_time=pharmacy_data.get('closing_time'),
                is_24_hours=pharmacy_data.get('is_24_hours', False)
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
        
        # Debug logging before sending email
        user_full_name = user.get_full_name
        verification_token = user.verification_token
        print(f"DEBUG: About to send email to {user.email}")
        print(f"DEBUG: User full name: '{user_full_name}'")
        print(f"DEBUG: Verification token: '{verification_token}'")
        print(f"DEBUG: Preferred language: '{user.preferred_language}'")
        
        # Send verification email with correct parameter order
        try:
            email_result = send_verification_email(
                user_email=user.email,
                user_name=user_full_name,  # This should be the actual name, not token
                verification_token=verification_token,  # This should be the token
                language=user.preferred_language
            )
            print(f"DEBUG: Email result: {email_result}")
            if not email_result['success']:
                # Log email failure but don't fail registration
                print(f"Failed to send verification email: {email_result.get('error')}")
        except Exception as e:
            print(f"Error sending verification email: {str(e)}")
            import traceback
            traceback.print_exc()
        
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
        print(f"Registration error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Registration failed: {str(e)}'
        }), 500

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Verify user email with token"""
    try:
        data = request.get_json()
        
        if not data or 'token' not in data:
            return jsonify({
                'success': False,
                'message': 'Verification token is required'
            }), 400
        
        token = data['token']
        
        # Find user with this verification token
        user = User.query.filter_by(verification_token=token).first()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired verification token'
            }), 400
        
        # Check if already verified
        if user.is_verified:
            return jsonify({
                'success': False,
                'message': 'Email is already verified'
            }), 400
        
        # Verify the user
        user.is_verified = True
        user.verification_token = None  # Clear the token
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Create access tokens for automatic login
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        # Log audit action
        log_audit_action(
            user.id,
            'verify_email',
            'user',
            user.id,
            f"Email verified for {user.email}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Email verified successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Email verification error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Email verification failed'
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        if 'email' not in data or 'password' not in data:
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
        
        # Check if email is verified
        if not user.is_verified:
            return jsonify({
                'success': False,
                'message': 'Please verify your email before logging in.',
                'requires_verification': True
            }), 403
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create access tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        # Log audit action
        log_audit_action(
            user.id,
            'login',
            'user',
            user.id,
            f"User logged in: {user.email}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Login error: {str(e)}")
        print("Login request data:", data)
        return jsonify({
            'success': False,
            'message': 'Login failed'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    try:
        current_user_id = get_jwt_identity()
        
        # Log audit action
        log_audit_action(
            current_user_id,
            'logout',
            'user',
            current_user_id,
            "User logged out"
        )
        
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Logout failed'
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
        access_token = create_access_token(identity=current_user_id)
        
        return jsonify({
            'success': True,
            'access_token': access_token
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Token refresh failed'
        }), 500

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Send password reset email"""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({
                'success': False,
                'message': 'Email is required'
            }), 400
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user:
            # Don't reveal if email exists or not
            return jsonify({
                'success': True,
                'message': 'If the email exists, a password reset link has been sent.'
            }), 200
        
        # Generate password reset token
        user.password_reset_token = secrets.token_urlsafe(32)
        user.password_reset_sent_at = datetime.utcnow()
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
            'message': 'If the email exists, a password reset link has been sent.'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Failed to process password reset request'
        }), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        required_fields = ['token', 'new_password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'{field} is required'
                }), 400
        
        # Find user with reset token
        user = User.query.filter_by(password_reset_token=data['token']).first()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired reset token'
            }), 400
        
        # Check if token is expired (24 hours)
        if user.password_reset_sent_at:
            token_age = datetime.utcnow() - user.password_reset_sent_at
            if token_age > timedelta(hours=24):
                return jsonify({
                    'success': False,
                    'message': 'Reset token has expired'
                }), 400
        
        # Validate new password
        password_validation = validate_password(data['new_password'])
        if not password_validation['valid']:
            return jsonify({
                'success': False,
                'message': password_validation['message']
            }), 400
        
        # Update password
        user.set_password(data['new_password'])
        user.password_reset_token = None
        user.password_reset_sent_at = None
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Log audit action
        log_audit_action(
            user.id,
            'password_reset',
            'user',
            user.id,
            f"Password reset for {user.email}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Password reset successful'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Password reset failed'
        }), 500

@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend email verification"""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({
                'success': False,
                'message': 'Email is required'
            }), 400
        
        # Validate email format
        if not validate_email(data['email']):
            return jsonify({
                'success': False,
                'message': 'Invalid email format'
            }), 400
        
        # Find user by email
        user = User.query.filter_by(email=data['email']).first()
        if not user:
            # Don't reveal if email exists or not for security
            return jsonify({
                'success': True,
                'message': 'If the email exists and is not verified, a verification email will be sent'
            }), 200
        
        # Check if user is already verified
        if user.is_verified:
            return jsonify({
                'success': False,
                'message': 'Email is already verified'
            }), 400
        
        # Generate new verification token
        user.generate_verification_token()
        db.session.commit()
        
        # Debug logging before sending email
        user_full_name = user.get_full_name()
        verification_token = user.verification_token
        print(f"DEBUG: About to resend email to {user.email}")
        print(f"DEBUG: User full name: '{user_full_name}'")
        print(f"DEBUG: Verification token: '{verification_token}'")
        print(f"DEBUG: Preferred language: '{user.preferred_language}'")
        
        # Send verification email
        try:
            email_result = send_verification_email(
                user_email=user.email,
                user_name=user_full_name,
                verification_token=verification_token,
                language=user.preferred_language
            )
            
            print(f"DEBUG: Email result: {email_result}")
            
            if not email_result.get('success', False):
                current_app.logger.error(f"Failed to send verification email: {email_result}")
                return jsonify({
                    'success': False,
                    'message': 'Failed to send verification email'
                }), 500
                
        except Exception as email_error:
            current_app.logger.error(f"Email sending error: {str(email_error)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': 'Failed to send verification email'
            }), 500
        
        # Log audit action
        log_audit_action(
            user.id,
            'verification_email_resent',
            'user',
            user.id,
            f"Verification email resent for {user.email}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Verification email sent successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Resend verification error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Failed to resend verification email'
        }), 500


