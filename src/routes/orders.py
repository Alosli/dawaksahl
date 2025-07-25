from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime

from src.models import db, Order, OrderItem, ShoppingCart, CartItem, OrderStatus, PaymentMethod, PaymentStatus
from src.utils.auth import get_current_user, log_audit_action, require_customer, require_seller_or_admin, can_access_order
from src.utils.validation import validate_required_fields, validate_order_status, validate_payment_method, sanitize_string
from src.utils.email import send_order_confirmation_email

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/', methods=['POST'])
@require_customer
def create_order():
    """Create new order from cart items"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['pharmacy_id', 'delivery_method', 'payment_method']
        validation_result = validate_required_fields(data, required_fields)
        if not validation_result['valid']:
            return jsonify({
                'success': False,
                'message': validation_result['message']
            }), 400
        
        # Get user's cart
        cart = ShoppingCart.query.filter_by(user_id=user.id).first()
        if not cart or not cart.items:
            return jsonify({
                'success': False,
                'message': 'Cart is empty'
            }), 400
        
        # Filter cart items by pharmacy
        pharmacy_items = [item for item in cart.items if item.pharmacy_id == data['pharmacy_id']]
        if not pharmacy_items:
            return jsonify({
                'success': False,
                'message': 'No items found for this pharmacy'
            }), 400
        
        # Create order
        order = Order(
            customer_id=user.id,
            pharmacy_id=data['pharmacy_id'],
            delivery_method=data['delivery_method'],
            payment_method=data['payment_method'],
            delivery_address=sanitize_string(data.get('delivery_address')),
            delivery_phone=sanitize_string(data.get('delivery_phone')),
            delivery_notes=sanitize_string(data.get('delivery_notes')),
            special_instructions=sanitize_string(data.get('special_instructions'))
        )
        
        # Generate order number
        order.order_number = order.generate_order_number()
        
        # Add order items
        subtotal = 0
        for cart_item in pharmacy_items:
            order_item = OrderItem(
                product_id=cart_item.product_id,
                product_name=cart_item.product_name,
                product_name_ar=cart_item.product_name_ar,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price
            )
            order_item.calculate_total()
            order.items.append(order_item)
            subtotal += order_item.total_price
        
        # Calculate totals
        order.subtotal = subtotal
        order.delivery_fee = data.get('delivery_fee', 0)
        order.tax_amount = data.get('tax_amount', 0)
        order.discount_amount = data.get('discount_amount', 0)
        order.calculate_totals()
        
        # Save order
        db.session.add(order)
        db.session.commit()
        
        # Remove items from cart
        for cart_item in pharmacy_items:
            db.session.delete(cart_item)
        cart.calculate_totals()
        db.session.commit()
        
        # Send order confirmation email
        try:
            email_result = send_order_confirmation_email(
                user.email,
                user.get_full_name(),
                order.to_dict(),
                user.preferred_language
            )
            if not email_result['success']:
                # Log email failure but don't fail the order
                print(f"Failed to send order confirmation email: {email_result.get('error')}")
        except Exception as e:
            print(f"Error sending order confirmation email: {str(e)}")
        
        # Log audit action
        log_audit_action(
            user.id,
            'create',
            'order',
            order.id,
            f"Created order {order.order_number}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Order created successfully',
            'order': order.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error creating order: {str(e)}'
        }), 500

@orders_bp.route('/', methods=['GET'])
@jwt_required()
def get_orders():
    """Get user's orders"""
    try:
        user = get_current_user()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        status = request.args.get('status')
        
        # Build query based on user type
        if user.user_type.value == 'customer':
            query = Order.query.filter_by(customer_id=user.id)
        elif user.user_type.value == 'seller':
            # Get orders for seller's pharmacy
            from src.models import Pharmacy
            pharmacy = Pharmacy.query.filter_by(seller_id=user.id).first()
            if not pharmacy:
                return jsonify({
                    'success': False,
                    'message': 'No pharmacy found for this seller'
                }), 404
            query = Order.query.filter_by(pharmacy_id=pharmacy.id)
        else:  # admin
            query = Order.query
        
        # Filter by status if provided
        if status:
            try:
                status_enum = OrderStatus(status)
                query = query.filter_by(status=status_enum)
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid order status'
                }), 400
        
        # Paginate results
        orders = query.order_by(Order.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'orders': [order.to_dict() for order in orders.items],
            'pagination': {
                'page': page,
                'pages': orders.pages,
                'per_page': per_page,
                'total': orders.total
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching orders: {str(e)}'
        }), 500

@orders_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order(order_id):
    """Get specific order details"""
    try:
        user = get_current_user()
        order = Order.query.get_or_404(order_id)
        
        # Check access permissions
        if not can_access_order(user, order):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        return jsonify({
            'success': True,
            'order': order.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching order: {str(e)}'
        }), 500

@orders_bp.route('/<int:order_id>/status', methods=['PUT'])
@require_seller_or_admin
def update_order_status(order_id):
    """Update order status"""
    try:
        user = get_current_user()
        order = Order.query.get_or_404(order_id)
        data = request.get_json()
        
        if not data or 'status' not in data:
            return jsonify({
                'success': False,
                'message': 'Status is required'
            }), 400
        
        # Validate status
        try:
            new_status = OrderStatus(data['status'])
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid order status'
            }), 400
        
        # Check permissions for sellers
        if user.user_type.value == 'seller':
            from src.models import Pharmacy
            pharmacy = Pharmacy.query.filter_by(seller_id=user.id).first()
            if not pharmacy or order.pharmacy_id != pharmacy.id:
                return jsonify({
                    'success': False,
                    'message': 'Access denied'
                }), 403
        
        # Update status
        old_status = order.status
        order.status = new_status
        
        # Update timestamps based on status
        if new_status == OrderStatus.DELIVERED:
            order.delivered_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(
            user.id,
            'update',
            'order',
            order.id,
            f"Updated order status from {old_status.value} to {new_status.value}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Order status updated successfully',
            'order': order.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating order status: {str(e)}'
        }), 500

@orders_bp.route('/<int:order_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_order(order_id):
    """Cancel an order"""
    try:
        user = get_current_user()
        order = Order.query.get_or_404(order_id)
        data = request.get_json() or {}
        
        # Check access permissions
        if not can_access_order(user, order):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Check if order can be cancelled
        if not order.can_be_cancelled():
            return jsonify({
                'success': False,
                'message': 'Order cannot be cancelled at this stage'
            }), 400
        
        # Update order status
        order.status = OrderStatus.CANCELLED
        order.cancellation_reason = sanitize_string(data.get('reason', 'Cancelled by user'))
        
        # Restore inventory (if needed)
        # This would be implemented based on your inventory management system
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(
            user.id,
            'update',
            'order',
            order.id,
            f"Cancelled order {order.order_number}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error cancelling order: {str(e)}'
        }), 500
