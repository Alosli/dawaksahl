from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.models import db, User, UserAddress
from src.utils.auth import get_current_user, log_audit_action, generate_api_response, require_verified_user
from src.utils.validation import validate_required_fields, validate_email, validate_phone, validate_coordinates, sanitize_string

users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Include addresses in profile
        profile_data = user.to_dict()
        profile_data['addresses'] = [addr.to_dict() for addr in user.addresses]
        
        return jsonify({
            'user': profile_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get profile error: {str(e)}")
        return jsonify({'error': 'Failed to get profile'}), 500

@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update current user profile"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Store old values for audit
        old_values = user.to_dict()
        
        # Update allowed fields
        updatable_fields = [
            'first_name', 'last_name', 'phone_number', 
            'preferred_language', 'profile_picture_url'
        ]
        
        for field in updatable_fields:
            if field in data:
                if field in ['first_name', 'last_name']:
                    # Sanitize name fields
                    value = sanitize_string(data[field], 100)
                    if not value:
                        return jsonify({'error': f'{field} cannot be empty'}), 400
                    setattr(user, field, value)
                
                elif field == 'phone_number':
                    if data[field]:
                        if not validate_phone(data[field]):
                            return jsonify({'error': 'Invalid phone number format'}), 400
                        
                        # Check if phone number is already taken by another user
                        existing_phone = User.query.filter(
                            User.phone_number == data[field],
                            User.id != user.id
                        ).first()
                        if existing_phone:
                            return jsonify({'error': 'Phone number already in use'}), 409
                    
                    setattr(user, field, data[field])
                
                elif field == 'preferred_language':
                    if data[field] not in ['ar', 'en']:
                        return jsonify({'error': 'Invalid language code'}), 400
                    setattr(user, field, data[field])
                
                else:
                    setattr(user, field, data[field])
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'profile_updated', 'users', user.id, old_values, user.to_dict())
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update profile error: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

@users_bp.route('/addresses', methods=['GET'])
@jwt_required()
def get_addresses():
    """Get user addresses"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        addresses = [addr.to_dict() for addr in user.addresses]
        
        return jsonify({
            'addresses': addresses
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get addresses error: {str(e)}")
        return jsonify({'error': 'Failed to get addresses'}), 500

@users_bp.route('/addresses', methods=['POST'])
@jwt_required()
def add_address():
    """Add new user address"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['district']
        validation = validate_required_fields(data, required_fields)
        if not validation['valid']:
            return jsonify({'error': validation['message']}), 400
        
        # Validate coordinates if provided
        if data.get('latitude') and data.get('longitude'):
            coord_validation = validate_coordinates(data['latitude'], data['longitude'])
            if not coord_validation['valid']:
                return jsonify({'error': coord_validation['message']}), 400
        
        # If this is the first address, make it primary
        is_primary = len(user.addresses) == 0 or data.get('is_primary', False)
        
        # If setting as primary, unset other primary addresses
        if is_primary:
            for addr in user.addresses:
                addr.is_primary = False
        
        # Create new address
        address = UserAddress(
            user_id=user.id,
            country=sanitize_string(data.get('country', 'Yemen'), 100),
            city=sanitize_string(data.get('city', 'Taiz'), 100),
            district=sanitize_string(data['district'], 100),
            detailed_address=sanitize_string(data.get('detailed_address', ''), 500),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            is_primary=is_primary
        )
        
        db.session.add(address)
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'address_added', 'user_addresses', address.id, {}, address.to_dict())
        
        return jsonify({
            'message': 'Address added successfully',
            'address': address.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Add address error: {str(e)}")
        return jsonify({'error': 'Failed to add address'}), 500

@users_bp.route('/addresses/<address_id>', methods=['PUT'])
@jwt_required()
def update_address(address_id):
    """Update user address"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        address = UserAddress.query.filter_by(id=address_id, user_id=user.id).first()
        if not address:
            return jsonify({'error': 'Address not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Store old values for audit
        old_values = address.to_dict()
        
        # Validate coordinates if provided
        if data.get('latitude') and data.get('longitude'):
            coord_validation = validate_coordinates(data['latitude'], data['longitude'])
            if not coord_validation['valid']:
                return jsonify({'error': coord_validation['message']}), 400
        
        # Update allowed fields
        updatable_fields = [
            'country', 'city', 'district', 'detailed_address', 
            'latitude', 'longitude', 'is_primary'
        ]
        
        for field in updatable_fields:
            if field in data:
                if field in ['country', 'city', 'district']:
                    value = sanitize_string(data[field], 100)
                    if field == 'district' and not value:
                        return jsonify({'error': 'District cannot be empty'}), 400
                    setattr(address, field, value)
                
                elif field == 'detailed_address':
                    setattr(address, field, sanitize_string(data[field], 500))
                
                elif field == 'is_primary':
                    if data[field]:
                        # Unset other primary addresses
                        for addr in user.addresses:
                            if addr.id != address.id:
                                addr.is_primary = False
                    setattr(address, field, data[field])
                
                else:
                    setattr(address, field, data[field])
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'address_updated', 'user_addresses', address.id, old_values, address.to_dict())
        
        return jsonify({
            'message': 'Address updated successfully',
            'address': address.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update address error: {str(e)}")
        return jsonify({'error': 'Failed to update address'}), 500

@users_bp.route('/addresses/<address_id>', methods=['DELETE'])
@jwt_required()
def delete_address(address_id):
    """Delete user address"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        address = UserAddress.query.filter_by(id=address_id, user_id=user.id).first()
        if not address:
            return jsonify({'error': 'Address not found'}), 404
        
        # Don't allow deletion of the only address
        if len(user.addresses) == 1:
            return jsonify({'error': 'Cannot delete the only address'}), 400
        
        # Store values for audit
        old_values = address.to_dict()
        
        # If deleting primary address, set another address as primary
        if address.is_primary:
            other_address = UserAddress.query.filter(
                UserAddress.user_id == user.id,
                UserAddress.id != address.id
            ).first()
            if other_address:
                other_address.is_primary = True
        
        db.session.delete(address)
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'address_deleted', 'user_addresses', address_id, old_values, {})
        
        return jsonify({
            'message': 'Address deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete address error: {str(e)}")
        return jsonify({'error': 'Failed to delete address'}), 500

@users_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['current_password', 'new_password']
        validation = validate_required_fields(data, required_fields)
        if not validation['valid']:
            return jsonify({'error': validation['message']}), 400
        
        # Verify current password
        if not user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Validate new password
        from src.utils.validation import validate_password
        password_validation = validate_password(data['new_password'])
        if not password_validation['valid']:
            return jsonify({'error': password_validation['message']}), 400
        
        # Check if new password is different from current
        if user.check_password(data['new_password']):
            return jsonify({'error': 'New password must be different from current password'}), 400
        
        # Update password
        user.set_password(data['new_password'])
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'password_changed', 'users', user.id, {}, {})
        
        return jsonify({
            'message': 'Password changed successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Change password error: {str(e)}")
        return jsonify({'error': 'Failed to change password'}), 500

@users_bp.route('/deactivate', methods=['POST'])
@jwt_required()
def deactivate_account():
    """Deactivate user account"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data or not data.get('password'):
            return jsonify({'error': 'Password confirmation required'}), 400
        
        # Verify password
        if not user.check_password(data['password']):
            return jsonify({'error': 'Password is incorrect'}), 400
        
        # Deactivate account
        user.is_active = False
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'account_deactivated', 'users', user.id, {'is_active': True}, {'is_active': False})
        
        return jsonify({
            'message': 'Account deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Deactivate account error: {str(e)}")
        return jsonify({'error': 'Failed to deactivate account'}), 500

