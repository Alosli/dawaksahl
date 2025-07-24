from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta

from src.models import db, User, Pharmacy, Product, ProductCategory, Order, District, SystemSetting, AuditLog, VerificationStatus
from src.utils.auth import get_current_user, log_audit_action, require_admin
from src.utils.validation import validate_required_fields, sanitize_string

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard', methods=['GET'])
@require_admin
def get_dashboard():
    """Get admin dashboard statistics"""
    try:
        # Get date range for statistics
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # User statistics
        total_users = User.query.count()
        new_users_week = User.query.filter(User.created_at >= week_ago).count()
        verified_users = User.query.filter_by(is_verified=True).count()
        
        # Pharmacy statistics
        total_pharmacies = Pharmacy.query.count()
        verified_pharmacies = Pharmacy.query.filter_by(is_verified=True).count()
        pending_pharmacies = Pharmacy.query.filter_by(is_verified=False).count()
        
        # Product statistics
        total_products = Product.query.count()
        active_products = Product.query.filter_by(is_active=True).count()
        
        # Order statistics
        total_orders = Order.query.count()
        orders_week = Order.query.filter(Order.created_at >= week_ago).count()
        orders_month = Order.query.filter(Order.created_at >= month_ago).count()
        
        # Revenue statistics (simplified)
        total_revenue = db.session.query(func.sum(Order.total_amount)).filter(
            Order.order_status.in_(['delivered', 'confirmed'])
        ).scalar() or 0
        
        revenue_month = db.session.query(func.sum(Order.total_amount)).filter(
            and_(
                Order.created_at >= month_ago,
                Order.order_status.in_(['delivered', 'confirmed'])
            )
        ).scalar() or 0
        
        # Recent activities
        recent_activities = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
        
        return jsonify({
            'statistics': {
                'users': {
                    'total': total_users,
                    'new_this_week': new_users_week,
                    'verified': verified_users,
                    'verification_rate': round((verified_users / total_users * 100) if total_users > 0 else 0, 1)
                },
                'pharmacies': {
                    'total': total_pharmacies,
                    'verified': verified_pharmacies,
                    'pending': pending_pharmacies,
                    'verification_rate': round((verified_pharmacies / total_pharmacies * 100) if total_pharmacies > 0 else 0, 1)
                },
                'products': {
                    'total': total_products,
                    'active': active_products
                },
                'orders': {
                    'total': total_orders,
                    'this_week': orders_week,
                    'this_month': orders_month
                },
                'revenue': {
                    'total': float(total_revenue),
                    'this_month': float(revenue_month)
                }
            },
            'recent_activities': [
                {
                    'id': activity.id,
                    'action_type': activity.action_type,
                    'user_id': activity.user_id,
                    'table_name': activity.table_name,
                    'created_at': activity.created_at.isoformat()
                }
                for activity in recent_activities
            ]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get dashboard error: {str(e)}")
        return jsonify({'error': 'Failed to get dashboard data'}), 500

@admin_bp.route('/users', methods=['GET'])
@require_admin
def get_users():
    """Get users list with filtering"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        user_type = request.args.get('user_type')
        status = request.args.get('status')  # active, inactive, verified, unverified
        search = request.args.get('search', '')
        
        # Build query
        query = User.query
        
        # Filter by user type
        if user_type and user_type in ['customer', 'seller', 'admin']:
            query = query.filter_by(user_type=user_type)
        
        # Filter by status
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        elif status == 'verified':
            query = query.filter_by(is_verified=True)
        elif status == 'unverified':
            query = query.filter_by(is_verified=False)
        
        # Search filter
        if search:
            query = query.filter(
                or_(
                    User.first_name.ilike(f'%{search}%'),
                    User.last_name.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%'),
                    User.phone_number.ilike(f'%{search}%')
                )
            )
        
        # Order by creation date
        query = query.order_by(User.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        users = [user.to_dict() for user in pagination.items]
        
        return jsonify({
            'users': users,
            'pagination': {
                'page': pagination.page,
                'pages': pagination.pages,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get users error: {str(e)}")
        return jsonify({'error': 'Failed to get users'}), 500

@admin_bp.route('/users/<user_id>/status', methods=['PUT'])
@require_admin
def update_user_status(user_id):
    """Update user account status"""
    try:
        admin_user = get_current_user()
        data = request.get_json()
        
        if not data or 'is_active' not in data:
            return jsonify({'error': 'is_active status is required'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Don't allow deactivating admin users
        if user.user_type.value == 'admin' and not data['is_active']:
            return jsonify({'error': 'Cannot deactivate admin users'}), 400
        
        # Store old values for audit
        old_values = {'is_active': user.is_active}
        
        # Update status
        user.is_active = data['is_active']
        reason = sanitize_string(data.get('reason', ''), 500)
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(admin_user.id, 'user_status_updated', 'users', user.id, old_values, {
            'is_active': user.is_active,
            'reason': reason
        })
        
        return jsonify({
            'message': 'User status updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update user status error: {str(e)}")
        return jsonify({'error': 'Failed to update user status'}), 500

@admin_bp.route('/pharmacies/pending', methods=['GET'])
@require_admin
def get_pending_pharmacies():
    """Get pharmacies pending verification"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Get unverified pharmacies
        query = Pharmacy.query.filter_by(is_verified=False).order_by(Pharmacy.created_at.asc())
        
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        pharmacies = []
        for pharmacy in pagination.items:
            pharmacy_data = pharmacy.to_dict()
            pharmacy_data['seller'] = pharmacy.seller.to_dict()
            pharmacy_data['documents'] = [doc.to_dict() for doc in pharmacy.documents]
            pharmacies.append(pharmacy_data)
        
        return jsonify({
            'pharmacies': pharmacies,
            'pagination': {
                'page': pagination.page,
                'pages': pagination.pages,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get pending pharmacies error: {str(e)}")
        return jsonify({'error': 'Failed to get pending pharmacies'}), 500

@admin_bp.route('/pharmacies/<pharmacy_id>/verify', methods=['PUT'])
@require_admin
def verify_pharmacy(pharmacy_id):
    """Verify or reject pharmacy registration"""
    try:
        admin_user = get_current_user()
        data = request.get_json()
        
        if not data or 'approved' not in data:
            return jsonify({'error': 'Approval decision is required'}), 400
        
        pharmacy = Pharmacy.query.get(pharmacy_id)
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        # Store old values for audit
        old_values = {'is_verified': pharmacy.is_verified}
        
        # Update verification status
        pharmacy.is_verified = data['approved']
        notes = sanitize_string(data.get('notes', ''), 500)
        
        # Update document verification status
        for document in pharmacy.documents:
            document.verification_status = VerificationStatus.APPROVED if data['approved'] else VerificationStatus.REJECTED
            document.admin_notes = notes
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(admin_user.id, 'pharmacy_verified', 'pharmacies', pharmacy.id, old_values, {
            'is_verified': pharmacy.is_verified,
            'notes': notes
        })
        
        status_text = 'approved' if data['approved'] else 'rejected'
        return jsonify({
            'message': f'Pharmacy {status_text} successfully',
            'pharmacy': pharmacy.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Verify pharmacy error: {str(e)}")
        return jsonify({'error': 'Failed to verify pharmacy'}), 500

@admin_bp.route('/products', methods=['GET'])
@require_admin
def get_products():
    """Get products for admin management"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '')
        category_id = request.args.get('category_id')
        status = request.args.get('status')  # active, inactive
        
        # Build query
        query = Product.query
        
        # Search filter
        if search:
            query = query.filter(
                or_(
                    Product.product_name.ilike(f'%{search}%'),
                    Product.product_name_ar.ilike(f'%{search}%'),
                    Product.generic_name.ilike(f'%{search}%'),
                    Product.brand_name.ilike(f'%{search}%')
                )
            )
        
        # Category filter
        if category_id:
            query = query.filter_by(category_id=category_id)
        
        # Status filter
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        
        # Order by name
        query = query.order_by(Product.product_name.asc())
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        products = [product.to_dict() for product in pagination.items]
        
        return jsonify({
            'products': products,
            'pagination': {
                'page': pagination.page,
                'pages': pagination.pages,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get products error: {str(e)}")
        return jsonify({'error': 'Failed to get products'}), 500

@admin_bp.route('/products', methods=['POST'])
@require_admin
def create_product():
    """Create new product in catalog"""
    try:
        admin_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['product_name']
        validation = validate_required_fields(data, required_fields)
        if not validation['valid']:
            return jsonify({'error': validation['message']}), 400
        
        # Create product
        product = Product(
            product_name=sanitize_string(data['product_name'], 300),
            product_name_ar=sanitize_string(data.get('product_name_ar', ''), 300),
            generic_name=sanitize_string(data.get('generic_name', ''), 300),
            generic_name_ar=sanitize_string(data.get('generic_name_ar', ''), 300),
            brand_name=sanitize_string(data.get('brand_name', ''), 200),
            brand_name_ar=sanitize_string(data.get('brand_name_ar', ''), 200),
            category_id=data.get('category_id'),
            manufacturer=sanitize_string(data.get('manufacturer', ''), 200),
            manufacturer_ar=sanitize_string(data.get('manufacturer_ar', ''), 200),
            description=sanitize_string(data.get('description', '')),
            description_ar=sanitize_string(data.get('description_ar', '')),
            dosage_form=sanitize_string(data.get('dosage_form', ''), 100),
            strength=sanitize_string(data.get('strength', ''), 100),
            pack_size=sanitize_string(data.get('pack_size', ''), 100),
            active_ingredients=sanitize_string(data.get('active_ingredients', '')),
            active_ingredients_ar=sanitize_string(data.get('active_ingredients_ar', '')),
            prescription_required=data.get('prescription_required', False),
            barcode=sanitize_string(data.get('barcode', ''), 100),
            sku=sanitize_string(data.get('sku', ''), 100),
            default_image_url=data.get('default_image_url'),
            created_by=admin_user.id
        )
        
        db.session.add(product)
        db.session.commit()
        
        # Log audit action
        log_audit_action(admin_user.id, 'product_created', 'products', product.id, {}, product.to_dict())
        
        return jsonify({
            'message': 'Product created successfully',
            'product': product.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create product error: {str(e)}")
        return jsonify({'error': 'Failed to create product'}), 500

@admin_bp.route('/settings', methods=['GET'])
@require_admin
def get_settings():
    """Get system settings"""
    try:
        settings = SystemSetting.query.all()
        
        settings_dict = {}
        for setting in settings:
            settings_dict[setting.setting_key] = {
                'value': setting.get_typed_value(),
                'type': setting.setting_type.value,
                'description': setting.description,
                'is_public': setting.is_public
            }
        
        return jsonify({
            'settings': settings_dict
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get settings error: {str(e)}")
        return jsonify({'error': 'Failed to get settings'}), 500

@admin_bp.route('/settings/<setting_key>', methods=['PUT'])
@require_admin
def update_setting(setting_key):
    """Update system setting"""
    try:
        admin_user = get_current_user()
        data = request.get_json()
        
        if not data or 'value' not in data:
            return jsonify({'error': 'Setting value is required'}), 400
        
        setting = SystemSetting.query.filter_by(setting_key=setting_key).first()
        if not setting:
            return jsonify({'error': 'Setting not found'}), 404
        
        # Store old value for audit
        old_value = setting.get_typed_value()
        
        # Update setting
        setting.set_typed_value(data['value'])
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(admin_user.id, 'setting_updated', 'system_settings', setting.id, 
                        {'value': old_value}, {'value': setting.get_typed_value()})
        
        return jsonify({
            'message': 'Setting updated successfully',
            'setting': {
                'key': setting.setting_key,
                'value': setting.get_typed_value(),
                'type': setting.setting_type.value
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update setting error: {str(e)}")
        return jsonify({'error': 'Failed to update setting'}), 500

@admin_bp.route('/districts', methods=['GET'])
@require_admin
def get_districts():
    """Get districts list"""
    try:
        districts = District.query.filter_by(is_active=True).order_by(District.sort_order).all()
        
        return jsonify({
            'districts': [district.to_dict() for district in districts]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get districts error: {str(e)}")
        return jsonify({'error': 'Failed to get districts'}), 500

