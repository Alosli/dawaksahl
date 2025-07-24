from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from src.models import db, Product, ProductCategory, PharmacyProduct
from src.utils.auth import get_current_user, log_audit_action, require_admin
from src.utils.validation import validate_required_fields, sanitize_string

products_bp = Blueprint('products', __name__)

@products_bp.route('/catalog', methods=['GET'])
def get_product_catalog():
    """Get product catalog (public endpoint)"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '')
        category_id = request.args.get('category_id')
        
        # Build query
        query = Product.query.filter_by(is_active=True)
        
        # Search filter
        if search:
            query = query.filter(
                db.or_(
                    Product.product_name.ilike(f'%{search}%'),
                    Product.product_name_ar.ilike(f'%{search}%'),
                    Product.generic_name.ilike(f'%{search}%'),
                    Product.brand_name.ilike(f'%{search}%')
                )
            )
        
        # Category filter
        if category_id:
            query = query.filter_by(category_id=category_id)
        
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
        current_app.logger.error(f"Get product catalog error: {str(e)}")
        return jsonify({'error': 'Failed to get product catalog'}), 500

@products_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get product categories"""
    try:
        categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.sort_order).all()
        return jsonify({
            'categories': [category.to_dict() for category in categories]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get categories error: {str(e)}")
        return jsonify({'error': 'Failed to get categories'}), 500

@products_bp.route('/<product_id>', methods=['GET'])
def get_product(product_id):
    """Get product details"""
    try:
        product = Product.query.get(product_id)
        if not product or not product.is_active:
            return jsonify({'error': 'Product not found'}), 404
        
        return jsonify({
            'product': product.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get product error: {str(e)}")
        return jsonify({'error': 'Failed to get product'}), 500

