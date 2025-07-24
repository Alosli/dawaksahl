from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from src.models import db, ShoppingCart, CartItem, PharmacyProduct, Product, Pharmacy
from src.utils.auth import get_current_user, log_audit_action, require_customer
from src.utils.validation import validate_required_fields, validate_quantity

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/', methods=['GET'])
@require_customer
def get_cart():
    """Get user's shopping cart"""
    try:
        user = get_current_user()
        
        # Get or create cart
        cart = ShoppingCart.query.filter_by(user_id=user.id).first()
        if not cart:
            cart = ShoppingCart(user_id=user.id)
            db.session.add(cart)
            db.session.commit()
        
        # Group items by pharmacy
        pharmacy_groups = {}
        total_amount = 0
        total_items = 0
        
        for item in cart.items:
            pharmacy_id = item.pharmacy_product.pharmacy_id
            
            if pharmacy_id not in pharmacy_groups:
                pharmacy = item.pharmacy_product.pharmacy
                pharmacy_groups[pharmacy_id] = {
                    'pharmacy': {
                        'id': pharmacy.id,
                        'pharmacy_name': pharmacy.pharmacy_name,
                        'pharmacy_name_ar': pharmacy.pharmacy_name_ar,
                        'district': pharmacy.district,
                        'phone_number': pharmacy.phone_number
                    },
                    'items': [],
                    'subtotal': 0
                }
            
            # Format item data
            item_data = {
                'id': item.id,
                'quantity': item.quantity,
                'total_price': item.get_total_price(),
                'pharmacy_product': item.pharmacy_product.to_dict(),
                'product': item.pharmacy_product.product.to_dict()
            }
            
            pharmacy_groups[pharmacy_id]['items'].append(item_data)
            pharmacy_groups[pharmacy_id]['subtotal'] += item.get_total_price()
            total_amount += item.get_total_price()
            total_items += item.quantity
        
        return jsonify({
            'cart': {
                'id': cart.id,
                'pharmacy_groups': list(pharmacy_groups.values()),
                'total_items': total_items,
                'total_amount': total_amount,
                'created_at': cart.created_at.isoformat(),
                'updated_at': cart.updated_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get cart error: {str(e)}")
        return jsonify({'error': 'Failed to get cart'}), 500

@cart_bp.route('/items', methods=['POST'])
@require_customer
def add_to_cart():
    """Add item to shopping cart"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['pharmacy_product_id', 'quantity']
        validation = validate_required_fields(data, required_fields)
        if not validation['valid']:
            return jsonify({'error': validation['message']}), 400
        
        # Validate quantity
        quantity_validation = validate_quantity(data['quantity'])
        if not quantity_validation['valid']:
            return jsonify({'error': quantity_validation['message']}), 400
        
        quantity = int(data['quantity'])
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400
        
        # Validate pharmacy product
        pharmacy_product = PharmacyProduct.query.get(data['pharmacy_product_id'])
        if not pharmacy_product:
            return jsonify({'error': 'Product not found'}), 404
        
        if not pharmacy_product.is_in_stock():
            return jsonify({'error': 'Product is not available'}), 400
        
        if not pharmacy_product.can_order_quantity(quantity):
            return jsonify({'error': f'Cannot order {quantity} items. Available: {pharmacy_product.quantity_available}'}), 400
        
        # Get or create cart
        cart = ShoppingCart.query.filter_by(user_id=user.id).first()
        if not cart:
            cart = ShoppingCart(user_id=user.id)
            db.session.add(cart)
            db.session.flush()
        
        # Check if item already exists in cart
        existing_item = CartItem.query.filter_by(
            cart_id=cart.id,
            pharmacy_product_id=data['pharmacy_product_id']
        ).first()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item.quantity + quantity
            if not pharmacy_product.can_order_quantity(new_quantity):
                return jsonify({'error': f'Cannot add {quantity} more items. Current in cart: {existing_item.quantity}, Available: {pharmacy_product.quantity_available}'}), 400
            
            old_values = {'quantity': existing_item.quantity}
            existing_item.quantity = new_quantity
            
            db.session.commit()
            
            # Log audit action
            log_audit_action(user.id, 'cart_item_updated', 'cart_items', existing_item.id, old_values, {'quantity': new_quantity})
            
            return jsonify({
                'message': 'Cart item updated successfully',
                'item': {
                    'id': existing_item.id,
                    'quantity': existing_item.quantity,
                    'total_price': existing_item.get_total_price()
                }
            }), 200
        else:
            # Create new cart item
            cart_item = CartItem(
                cart_id=cart.id,
                pharmacy_product_id=data['pharmacy_product_id'],
                quantity=quantity
            )
            
            db.session.add(cart_item)
            db.session.commit()
            
            # Log audit action
            log_audit_action(user.id, 'cart_item_added', 'cart_items', cart_item.id, {}, cart_item.to_dict())
            
            return jsonify({
                'message': 'Item added to cart successfully',
                'item': {
                    'id': cart_item.id,
                    'quantity': cart_item.quantity,
                    'total_price': cart_item.get_total_price()
                }
            }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Add to cart error: {str(e)}")
        return jsonify({'error': 'Failed to add item to cart'}), 500

@cart_bp.route('/items/<cart_item_id>', methods=['PUT'])
@require_customer
def update_cart_item(cart_item_id):
    """Update cart item quantity"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data or 'quantity' not in data:
            return jsonify({'error': 'Quantity is required'}), 400
        
        # Validate quantity
        quantity_validation = validate_quantity(data['quantity'])
        if not quantity_validation['valid']:
            return jsonify({'error': quantity_validation['message']}), 400
        
        quantity = int(data['quantity'])
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400
        
        # Get cart item
        cart_item = CartItem.query.join(ShoppingCart).filter(
            CartItem.id == cart_item_id,
            ShoppingCart.user_id == user.id
        ).first()
        
        if not cart_item:
            return jsonify({'error': 'Cart item not found'}), 404
        
        # Check if quantity is available
        if not cart_item.pharmacy_product.can_order_quantity(quantity):
            return jsonify({'error': f'Cannot order {quantity} items. Available: {cart_item.pharmacy_product.quantity_available}'}), 400
        
        # Update quantity
        old_values = {'quantity': cart_item.quantity}
        cart_item.quantity = quantity
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'cart_item_updated', 'cart_items', cart_item.id, old_values, {'quantity': quantity})
        
        return jsonify({
            'message': 'Cart item updated successfully',
            'item': {
                'id': cart_item.id,
                'quantity': cart_item.quantity,
                'total_price': cart_item.get_total_price()
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update cart item error: {str(e)}")
        return jsonify({'error': 'Failed to update cart item'}), 500

@cart_bp.route('/items/<cart_item_id>', methods=['DELETE'])
@require_customer
def remove_cart_item(cart_item_id):
    """Remove item from cart"""
    try:
        user = get_current_user()
        
        # Get cart item
        cart_item = CartItem.query.join(ShoppingCart).filter(
            CartItem.id == cart_item_id,
            ShoppingCart.user_id == user.id
        ).first()
        
        if not cart_item:
            return jsonify({'error': 'Cart item not found'}), 404
        
        # Store values for audit
        old_values = cart_item.to_dict()
        
        db.session.delete(cart_item)
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'cart_item_removed', 'cart_items', cart_item_id, old_values, {})
        
        return jsonify({
            'message': 'Item removed from cart successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Remove cart item error: {str(e)}")
        return jsonify({'error': 'Failed to remove cart item'}), 500

@cart_bp.route('/clear', methods=['DELETE'])
@require_customer
def clear_cart():
    """Clear entire shopping cart"""
    try:
        user = get_current_user()
        
        # Get cart
        cart = ShoppingCart.query.filter_by(user_id=user.id).first()
        if not cart:
            return jsonify({'message': 'Cart is already empty'}), 200
        
        # Remove all items
        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'cart_cleared', 'shopping_carts', cart.id, {}, {})
        
        return jsonify({
            'message': 'Cart cleared successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Clear cart error: {str(e)}")
        return jsonify({'error': 'Failed to clear cart'}), 500

@cart_bp.route('/count', methods=['GET'])
@require_customer
def get_cart_count():
    """Get cart item count"""
    try:
        user = get_current_user()
        
        # Get cart
        cart = ShoppingCart.query.filter_by(user_id=user.id).first()
        if not cart:
            return jsonify({'count': 0}), 200
        
        total_items = sum(item.quantity for item in cart.items)
        
        return jsonify({
            'count': total_items
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get cart count error: {str(e)}")
        return jsonify({'error': 'Failed to get cart count'}), 500

