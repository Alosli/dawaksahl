from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from datetime import time

from src.models import db, Pharmacy, PharmacyOperatingHours, PharmacyDocument, PharmacyProduct, Product, VerificationStatus, DocumentType
from src.utils.auth import get_current_user, log_audit_action, require_seller, require_seller_or_admin, can_access_pharmacy
from src.utils.validation import validate_required_fields, validate_coordinates, validate_price, validate_quantity, sanitize_string

pharmacies_bp = Blueprint('pharmacies', __name__)

@pharmacies_bp.route('/profile', methods=['GET'])
@require_seller
def get_pharmacy_profile():
    """Get pharmacy profile for authenticated seller"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        # Include related data
        profile_data = pharmacy.to_dict()
        profile_data['operating_hours'] = [hours.to_dict() for hours in pharmacy.operating_hours]
        profile_data['documents'] = [doc.to_dict() for doc in pharmacy.documents]
        
        return jsonify({
            'pharmacy': profile_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get pharmacy profile error: {str(e)}")
        return jsonify({'error': 'Failed to get pharmacy profile'}), 500

@pharmacies_bp.route('/profile', methods=['PUT'])
@require_seller
def update_pharmacy_profile():
    """Update pharmacy profile"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Store old values for audit
        old_values = pharmacy.to_dict()
        
        # Validate coordinates if provided
        if data.get('latitude') and data.get('longitude'):
            coord_validation = validate_coordinates(data['latitude'], data['longitude'])
            if not coord_validation['valid']:
                return jsonify({'error': coord_validation['message']}), 400
        
        # Update allowed fields
        updatable_fields = [
            'pharmacy_name', 'pharmacy_name_ar', 'description', 'description_ar',
            'phone_number', 'email', 'website_url', 'facebook_url', 'instagram_url',
            'whatsapp_number', 'district', 'detailed_address', 'latitude', 'longitude'
        ]
        
        for field in updatable_fields:
            if field in data:
                if field in ['pharmacy_name', 'district']:
                    # Required fields
                    value = sanitize_string(data[field], 200 if field == 'pharmacy_name' else 100)
                    if not value:
                        return jsonify({'error': f'{field} cannot be empty'}), 400
                    setattr(pharmacy, field, value)
                
                elif field in ['pharmacy_name_ar', 'description', 'description_ar', 'detailed_address']:
                    # Optional text fields
                    max_length = 200 if 'name' in field else None
                    setattr(pharmacy, field, sanitize_string(data[field], max_length))
                
                elif field in ['phone_number', 'whatsapp_number']:
                    # Phone number fields
                    if data[field]:
                        from src.utils.validation import validate_phone
                        if not validate_phone(data[field]):
                            return jsonify({'error': f'Invalid {field} format'}), 400
                    setattr(pharmacy, field, data[field])
                
                elif field == 'email':
                    # Email field
                    if data[field]:
                        from src.utils.validation import validate_email
                        if not validate_email(data[field]):
                            return jsonify({'error': 'Invalid email format'}), 400
                    setattr(pharmacy, field, data[field])
                
                else:
                    setattr(pharmacy, field, data[field])
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'pharmacy_updated', 'pharmacies', pharmacy.id, old_values, pharmacy.to_dict())
        
        return jsonify({
            'message': 'Pharmacy profile updated successfully',
            'pharmacy': pharmacy.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update pharmacy profile error: {str(e)}")
        return jsonify({'error': 'Failed to update pharmacy profile'}), 500

@pharmacies_bp.route('/operating-hours', methods=['GET'])
@require_seller
def get_operating_hours():
    """Get pharmacy operating hours"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        hours = [hour.to_dict() for hour in pharmacy.operating_hours]
        
        return jsonify({
            'operating_hours': hours
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get operating hours error: {str(e)}")
        return jsonify({'error': 'Failed to get operating hours'}), 500

@pharmacies_bp.route('/operating-hours', methods=['POST'])
@require_seller
def set_operating_hours():
    """Set pharmacy operating hours"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        data = request.get_json()
        if not data or 'hours' not in data:
            return jsonify({'error': 'Operating hours data required'}), 400
        
        # Clear existing hours
        PharmacyOperatingHours.query.filter_by(pharmacy_id=pharmacy.id).delete()
        
        # Add new hours
        for hour_data in data['hours']:
            if 'day_of_week' not in hour_data:
                return jsonify({'error': 'day_of_week is required for each hour entry'}), 400
            
            # Validate day of week
            day_of_week = hour_data['day_of_week']
            if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
                return jsonify({'error': 'day_of_week must be between 0 and 6'}), 400
            
            # Parse times
            opening_time = None
            closing_time = None
            break_start_time = None
            break_end_time = None
            
            if not hour_data.get('is_closed', False):
                if hour_data.get('opening_time'):
                    try:
                        opening_time = time.fromisoformat(hour_data['opening_time'])
                    except ValueError:
                        return jsonify({'error': f'Invalid opening_time format for day {day_of_week}'}), 400
                
                if hour_data.get('closing_time'):
                    try:
                        closing_time = time.fromisoformat(hour_data['closing_time'])
                    except ValueError:
                        return jsonify({'error': f'Invalid closing_time format for day {day_of_week}'}), 400
                
                if hour_data.get('break_start_time'):
                    try:
                        break_start_time = time.fromisoformat(hour_data['break_start_time'])
                    except ValueError:
                        return jsonify({'error': f'Invalid break_start_time format for day {day_of_week}'}), 400
                
                if hour_data.get('break_end_time'):
                    try:
                        break_end_time = time.fromisoformat(hour_data['break_end_time'])
                    except ValueError:
                        return jsonify({'error': f'Invalid break_end_time format for day {day_of_week}'}), 400
            
            operating_hour = PharmacyOperatingHours(
                pharmacy_id=pharmacy.id,
                day_of_week=day_of_week,
                opening_time=opening_time,
                closing_time=closing_time,
                is_closed=hour_data.get('is_closed', False),
                break_start_time=break_start_time,
                break_end_time=break_end_time
            )
            
            db.session.add(operating_hour)
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'operating_hours_updated', 'pharmacy_operating_hours', pharmacy.id, {}, {})
        
        return jsonify({
            'message': 'Operating hours updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Set operating hours error: {str(e)}")
        return jsonify({'error': 'Failed to set operating hours'}), 500

@pharmacies_bp.route('/documents', methods=['GET'])
@require_seller
def get_documents():
    """Get pharmacy documents"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        documents = [doc.to_dict() for doc in pharmacy.documents]
        
        return jsonify({
            'documents': documents
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get documents error: {str(e)}")
        return jsonify({'error': 'Failed to get documents'}), 500

@pharmacies_bp.route('/documents', methods=['POST'])
@require_seller
def upload_document():
    """Upload pharmacy document"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        document_type = request.form.get('document_type')
        document_name = request.form.get('document_name')
        
        if not document_type:
            return jsonify({'error': 'Document type is required'}), 400
        
        # Validate document type
        try:
            doc_type = DocumentType(document_type)
        except ValueError:
            return jsonify({'error': 'Invalid document type'}), 400
        
        # Validate file
        from src.utils.validation import validate_file_upload
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
        max_size = 16 * 1024 * 1024  # 16MB
        
        file_validation = validate_file_upload(file, allowed_extensions, max_size)
        if not file_validation['valid']:
            return jsonify({'error': file_validation['message']}), 400
        
        # TODO: Implement file upload to storage service
        # For now, we'll just store a placeholder URL
        document_url = f"/uploads/pharmacy_documents/{pharmacy.id}/{file.filename}"
        
        # Create document record
        document = PharmacyDocument(
            pharmacy_id=pharmacy.id,
            document_type=doc_type,
            document_url=document_url,
            document_name=document_name or file.filename,
            verification_status=VerificationStatus.PENDING
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'document_uploaded', 'pharmacy_documents', document.id, {}, document.to_dict())
        
        return jsonify({
            'message': 'Document uploaded successfully',
            'document': document.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Upload document error: {str(e)}")
        return jsonify({'error': 'Failed to upload document'}), 500

@pharmacies_bp.route('/products', methods=['GET'])
@require_seller
def get_pharmacy_products():
    """Get pharmacy product inventory"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '')
        category_id = request.args.get('category_id')
        availability = request.args.get('availability')  # 'available', 'out_of_stock'
        
        # Build query
        query = PharmacyProduct.query.filter_by(pharmacy_id=pharmacy.id)
        
        # Join with product for search
        if search:
            query = query.join(Product).filter(
                db.or_(
                    Product.product_name.ilike(f'%{search}%'),
                    Product.product_name_ar.ilike(f'%{search}%'),
                    Product.generic_name.ilike(f'%{search}%'),
                    Product.brand_name.ilike(f'%{search}%')
                )
            )
        
        # Filter by category
        if category_id:
            query = query.join(Product).filter(Product.category_id == category_id)
        
        # Filter by availability
        if availability == 'available':
            query = query.filter(
                PharmacyProduct.is_available == True,
                PharmacyProduct.quantity_available > 0
            )
        elif availability == 'out_of_stock':
            query = query.filter(
                db.or_(
                    PharmacyProduct.is_available == False,
                    PharmacyProduct.quantity_available <= 0
                )
            )
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format results
        products = []
        for pharmacy_product in pagination.items:
            product_data = pharmacy_product.to_dict()
            product_data['product'] = pharmacy_product.product.to_dict()
            products.append(product_data)
        
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
        current_app.logger.error(f"Get pharmacy products error: {str(e)}")
        return jsonify({'error': 'Failed to get pharmacy products'}), 500

@pharmacies_bp.route('/products', methods=['POST'])
@require_seller
def add_pharmacy_product():
    """Add product to pharmacy inventory"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['product_id', 'price', 'quantity_available']
        validation = validate_required_fields(data, required_fields)
        if not validation['valid']:
            return jsonify({'error': validation['message']}), 400
        
        # Validate product exists
        product = Product.query.get(data['product_id'])
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Check if product already exists in pharmacy
        existing = PharmacyProduct.query.filter_by(
            pharmacy_id=pharmacy.id,
            product_id=data['product_id']
        ).first()
        if existing:
            return jsonify({'error': 'Product already exists in pharmacy inventory'}), 409
        
        # Validate price and quantity
        price_validation = validate_price(data['price'])
        if not price_validation['valid']:
            return jsonify({'error': price_validation['message']}), 400
        
        quantity_validation = validate_quantity(data['quantity_available'])
        if not quantity_validation['valid']:
            return jsonify({'error': quantity_validation['message']}), 400
        
        # Create pharmacy product
        pharmacy_product = PharmacyProduct(
            pharmacy_id=pharmacy.id,
            product_id=data['product_id'],
            price=data['price'],
            quantity_available=data['quantity_available'],
            minimum_quantity=data.get('minimum_quantity', 1),
            maximum_quantity=data.get('maximum_quantity'),
            custom_image_url=data.get('custom_image_url'),
            pharmacy_notes=sanitize_string(data.get('pharmacy_notes', '')),
            pharmacy_notes_ar=sanitize_string(data.get('pharmacy_notes_ar', '')),
            is_available=data.get('is_available', True)
        )
        
        db.session.add(pharmacy_product)
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'product_added', 'pharmacy_products', pharmacy_product.id, {}, pharmacy_product.to_dict())
        
        # Include product details in response
        result = pharmacy_product.to_dict()
        result['product'] = product.to_dict()
        
        return jsonify({
            'message': 'Product added to inventory successfully',
            'pharmacy_product': result
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Add pharmacy product error: {str(e)}")
        return jsonify({'error': 'Failed to add product to inventory'}), 500

@pharmacies_bp.route('/products/<pharmacy_product_id>', methods=['PUT'])
@require_seller
def update_pharmacy_product(pharmacy_product_id):
    """Update pharmacy product"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        pharmacy_product = PharmacyProduct.query.filter_by(
            id=pharmacy_product_id,
            pharmacy_id=pharmacy.id
        ).first()
        
        if not pharmacy_product:
            return jsonify({'error': 'Product not found in inventory'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Store old values for audit
        old_values = pharmacy_product.to_dict()
        
        # Update allowed fields
        updatable_fields = [
            'price', 'quantity_available', 'minimum_quantity', 'maximum_quantity',
            'custom_image_url', 'pharmacy_notes', 'pharmacy_notes_ar', 'is_available'
        ]
        
        for field in updatable_fields:
            if field in data:
                if field == 'price':
                    price_validation = validate_price(data[field])
                    if not price_validation['valid']:
                        return jsonify({'error': price_validation['message']}), 400
                    setattr(pharmacy_product, field, data[field])
                
                elif field in ['quantity_available', 'minimum_quantity', 'maximum_quantity']:
                    if data[field] is not None:
                        quantity_validation = validate_quantity(data[field])
                        if not quantity_validation['valid']:
                            return jsonify({'error': f'{field}: {quantity_validation["message"]}'}), 400
                    setattr(pharmacy_product, field, data[field])
                
                elif field in ['pharmacy_notes', 'pharmacy_notes_ar']:
                    setattr(pharmacy_product, field, sanitize_string(data[field]))
                
                else:
                    setattr(pharmacy_product, field, data[field])
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'product_updated', 'pharmacy_products', pharmacy_product.id, old_values, pharmacy_product.to_dict())
        
        # Include product details in response
        result = pharmacy_product.to_dict()
        result['product'] = pharmacy_product.product.to_dict()
        
        return jsonify({
            'message': 'Product updated successfully',
            'pharmacy_product': result
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update pharmacy product error: {str(e)}")
        return jsonify({'error': 'Failed to update product'}), 500

@pharmacies_bp.route('/products/<pharmacy_product_id>', methods=['DELETE'])
@require_seller
def remove_pharmacy_product(pharmacy_product_id):
    """Remove product from pharmacy inventory"""
    try:
        user = get_current_user()
        pharmacy = user.pharmacy
        
        if not pharmacy:
            return jsonify({'error': 'Pharmacy not found'}), 404
        
        pharmacy_product = PharmacyProduct.query.filter_by(
            id=pharmacy_product_id,
            pharmacy_id=pharmacy.id
        ).first()
        
        if not pharmacy_product:
            return jsonify({'error': 'Product not found in inventory'}), 404
        
        # Store values for audit
        old_values = pharmacy_product.to_dict()
        
        db.session.delete(pharmacy_product)
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'product_removed', 'pharmacy_products', pharmacy_product_id, old_values, {})
        
        return jsonify({
            'message': 'Product removed from inventory successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Remove pharmacy product error: {str(e)}")
        return jsonify({'error': 'Failed to remove product from inventory'}), 500

