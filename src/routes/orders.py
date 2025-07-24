from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from datetime import datetime

from src.models import db, Order, OrderItem, ShoppingCart, CartItem, OrderStatus, PaymentMethod, PaymentStatus
from src.utils.auth import get_current_user, log_audit_action, require_customer, require_seller_or_admin, can_access_order
from src.utils.validation import validate_required_fields, validate_order_status, validate_payment_method, sanitize_string
from src.utils.email import send_order_notification_email

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/', methods=['POST'])
@require_customer
def create_order():
    """Create new order from cart items"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['delivery_address', 'payment_method']
        validation = validate_required_fields(data, required_fields)
        if not validation['valid']:
            return jsonify({'error': validation['message']}), 400
        
        # Validate payment method
        if not validate_payment_method(data['payment_method']):
            return jsonify({'error': 'Invalid payment method'}), 400
        
        # Get user's cart
        cart = ShoppingCart.query.filter_by(user_id=user.id).first()
        if not cart or not cart.items:
            return jsonify({'error': 'Cart is empty'}), 400
        
        # Group cart items by pharmacy
        pharmacy_groups = cart.get_items_by_pharmacy()
        
        if not pharmacy_groups:
            return jsonify({'error': 'No items in cart'}), 400
        
        created_orders = []
        
        # Create separate order for each pharmacy
        for pharmacy_id, items in pharmacy_groups.items():
            # Calculate order totals
            subtotal = sum(item.get_total_price() for item in items)
            delivery_fee = data.get('delivery_fee', 0.0)
            tax_amount = data.get('tax_amount', 0.0)
            discount_amount = data.get('discount_amount', 0.0)
            total_amount = subtotal + delivery_fee + tax_amount - discount_amount
            
            # Create order
            order = Order(
                user_id=user.id,
                pharmacy_id=pharmacy_id,
                total_amount=total_amount,
                delivery_fee=delivery_fee,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                payment_method=PaymentMethod(data['payment_method']),
                delivery_address=sanitize_string(data['delivery_address'], 500),
                delivery_latitude=data.get('delivery_latitude'),
                delivery_longitude=data.get('delivery_longitude'),
                customer_notes=sanitize_string(data.get('customer_notes', ''), 500)
            )
            
            db.session.add(order)
            db.session.flush()  # Get order ID
            
            # Create order items
            for cart_item in items:
                # Verify product availability
                if not cart_item.pharmacy_product.can_order_quantity(cart_item.quantity):
                    db.session.rollback()
                    return jsonify({
                        'error': f'Product {cart_item.pharmacy_product.product.product_name} is no longer available in requested quantity'
                    }), 400
                
                order_item = OrderItem(
                    order_id=order.id,
                    pharmacy_product_id=cart_item.pharmacy_product_id,
                    product_name=cart_item.pharmacy_product.product.product_name,
                    quantity=cart_item.quantity,
                    unit_price=cart_item.pharmacy_product.price,
                    total_price=cart_item.get_total_price()
                )
                
                db.session.add(order_item)
                
                # Update product quantity
                cart_item.pharmacy_product.quantity_available -= cart_item.quantity
            
            created_orders.append(order)
        
        # Clear cart after successful order creation
        CartItem.query.filter_by(cart_id=cart.id).delete()
        
        db.session.commit()
        
        # Send notification emails
        for order in created_orders:
            try:
                send_order_notification_email(user.email, order, user.preferred_language)
            except Exception as e:
                current_app.logger.error(f"Failed to send order notification: {str(e)}")
        
        # Log audit actions
        for order in created_orders:
            log_audit_action(user.id, 'order_created', 'orders', order.id, {}, order.to_dict())
        
        # Format response
        orders_data = []
        for order in created_orders:
            order_data = order.to_dict()
            order_data['items'] = [item.to_dict() for item in order.items]
            orders_data.append(order_data)
        
        return jsonify({
            'message': f'{len(created_orders)} order(s) created successfully',
            'orders': orders_data
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create order error: {str(e)}")
        return jsonify({'error': 'Failed to create order'}), 500

@orders_bp.route('/', methods=['GET'])
@jwt_required()
def get_orders():
    """Get user's orders (customers) or pharmacy orders (sellers)"""
    try:
        user = get_current_user()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status')
        
        # Build query based on user type
        if user.user_type.value == 'customer':
            query = Order.query.filter_by(user_id=user.id)
        elif user.user_type.value == 'seller':
            if not user.pharmacy:
                return jsonify({'error': 'Pharmacy not found'}), 404
            query = Order.query.filter_by(pharmacy_id=user.pharmacy.id)
        elif user.user_type.value == 'admin':
            query = Order.query
        else:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Filter by status
        if status and validate_order_status(status):
            query = query.filter_by(order_status=OrderStatus(status))
        
        # Order by creation date (newest first)
        query = query.order_by(Order.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format results
        orders = []
        for order in pagination.items:
            order_data = order.to_dict()
            order_data['items'] = [item.to_dict() for item in order.items]
            
            # Include customer info for sellers/admins
            if user.user_type.value in ['seller', 'admin']:
                order_data['customer'] = {
                    'id': order.customer.id,
                    'full_name': order.customer.get_full_name(),
                    'email': order.customer.email,
                    'phone_number': order.customer.phone_number
                }
            
            # Include pharmacy info for customers/admins
            if user.user_type.value in ['customer', 'admin']:
                order_data['pharmacy'] = {
                    'id': order.pharmacy.id,
                    'pharmacy_name': order.pharmacy.pharmacy_name,
                    'pharmacy_name_ar': order.pharmacy.pharmacy_name_ar,
                    'district': order.pharmacy.district,
                    'phone_number': order.pharmacy.phone_number
                }
            
            orders.append(order_data)
        
        return jsonify({
            'orders': orders,
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
        current_app.logger.error(f"Get orders error: {str(e)}")
        return jsonify({'error': 'Failed to get orders'}), 500

@orders_bp.route('/<order_id>', methods=['GET'])
@jwt_required()
def get_order(order_id):
    """Get specific order details"""
    try:
        user = get_current_user()
        order = Order.query.get(order_id)
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Check access permissions
        if not can_access_order(user, order):
            return jsonify({'error': 'Access denied'}), 403
        
        # Format order data
        order_data = order.to_dict()
        order_data['items'] = [item.to_dict() for item in order.items]
        
        # Include customer info for sellers/admins
        if user.user_type.value in ['seller', 'admin']:
            order_data['customer'] = {
                'id': order.customer.id,
                'full_name': order.customer.get_full_name(),
                'email': order.customer.email,
                'phone_number': order.customer.phone_number
            }
        
        # Include pharmacy info for customers/admins
        if user.user_type.value in ['customer', 'admin']:
            order_data['pharmacy'] = {
                'id': order.pharmacy.id,
                'pharmacy_name': order.pharmacy.pharmacy_name,
                'pharmacy_name_ar': order.pharmacy.pharmacy_name_ar,
                'district': order.pharmacy.district,
                'phone_number': order.pharmacy.phone_number,
                'detailed_address': order.pharmacy.detailed_address
            }
        
        return jsonify({
            'order': order_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get order error: {str(e)}")
        return jsonify({'error': 'Failed to get order'}), 500

@orders_bp.route('/<order_id>/status', methods=['PUT'])
@require_seller_or_admin
def update_order_status(order_id):
    """Update order status (sellers and admins only)"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data or 'status' not in data:
            return jsonify({'error': 'Status is required'}), 400
        
        # Validate status
        if not validate_order_status(data['status']):
            return jsonify({'error': 'Invalid order status'}), 400
        
        new_status = OrderStatus(data['status'])
        
        # Get order
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Check access permissions
        if not can_access_order(user, order):
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if status transition is valid
        if not order.can_update_status(new_status):
            return jsonify({'error': f'Cannot change status from {order.order_status.value} to {new_status.value}'}), 400
        
        # Store old values for audit
        old_values = {'order_status': order.order_status.value}
        
        # Update status
        order.order_status = new_status
        
        # Update delivery time if delivered
        if new_status == OrderStatus.DELIVERED:
            order.actual_delivery_time = datetime.utcnow()
        
        # Add pharmacy notes if provided
        if data.get('notes'):
            order.pharmacy_notes = sanitize_string(data['notes'], 500)
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'order_status_updated', 'orders', order.id, old_values, {
            'order_status': new_status.value,
            'pharmacy_notes': order.pharmacy_notes
        })
        
        return jsonify({
            'message': 'Order status updated successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update order status error: {str(e)}")
        return jsonify({'error': 'Failed to update order status'}), 500

@orders_bp.route('/<order_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_order(order_id):
    """Cancel order (customers and sellers)"""
    try:
        user = get_current_user()
        data = request.get_json() or {}
        
        # Get order
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Check access permissions
        if not can_access_order(user, order):
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if order can be cancelled
        if not order.can_cancel():
            return jsonify({'error': f'Cannot cancel order with status {order.order_status.value}'}), 400
        
        # Store old values for audit
        old_values = {'order_status': order.order_status.value}
        
        # Cancel order
        order.order_status = OrderStatus.CANCELLED
        
        # Add cancellation reason
        cancellation_reason = sanitize_string(data.get('reason', ''), 500)
        if user.user_type.value == 'customer':
            order.customer_notes = f"Cancelled by customer: {cancellation_reason}" if cancellation_reason else "Cancelled by customer"
        else:
            order.pharmacy_notes = f"Cancelled by pharmacy: {cancellation_reason}" if cancellation_reason else "Cancelled by pharmacy"
        
        # Restore product quantities
        for item in order.items:
            item.pharmacy_product.quantity_available += item.quantity
        
        db.session.commit()
        
        # Log audit action
        log_audit_action(user.id, 'order_cancelled', 'orders', order.id, old_values, {
            'order_status': OrderStatus.CANCELLED.value,
            'cancellation_reason': cancellation_reason
        })
        
        return jsonify({
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Cancel order error: {str(e)}")
        return jsonify({'error': 'Failed to cancel order'}), 500

