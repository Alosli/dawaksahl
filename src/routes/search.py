from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func, and_, or_

from src.models import db, Product, Pharmacy, ProductCategory
from src.utils.validation import sanitize_string

search_bp = Blueprint('search', __name__)

@search_bp.route('/products', methods=['GET'])
def search_products():
    """Search products across all pharmacies"""
    try:
        # Get query parameters
        query = request.args.get('query', '').strip()
        category_id = request.args.get('category_id')
        district = request.args.get('district')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        sort_by = request.args.get('sort_by', 'relevance')  # relevance, price_asc, price_desc, name
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Build base query
        base_query = db.session.query(
            PharmacyProduct,
            Product,
            Pharmacy
        ).join(
            Product, PharmacyProduct.product_id == Product.id
        ).join(
            Pharmacy, PharmacyProduct.pharmacy_id == Pharmacy.id
        ).filter(
            and_(
                Product.is_active == True,
                PharmacyProduct.is_available == True,
                PharmacyProduct.quantity_available > 0,
                Pharmacy.is_active == True,
                Pharmacy.is_verified == True
            )
        )
        
        # Search filter
        if query:
            search_filter = or_(
                Product.product_name.ilike(f'%{query}%'),
                Product.product_name_ar.ilike(f'%{query}%'),
                Product.generic_name.ilike(f'%{query}%'),
                Product.generic_name_ar.ilike(f'%{query}%'),
                Product.brand_name.ilike(f'%{query}%'),
                Product.brand_name_ar.ilike(f'%{query}%'),
                Product.active_ingredients.ilike(f'%{query}%'),
                Product.active_ingredients_ar.ilike(f'%{query}%')
            )
            base_query = base_query.filter(search_filter)
        
        # Category filter
        if category_id:
            base_query = base_query.filter(Product.category_id == category_id)
        
        # District filter
        if district:
            base_query = base_query.filter(Pharmacy.district.ilike(f'%{district}%'))
        
        # Price filters
        if min_price is not None:
            base_query = base_query.filter(PharmacyProduct.price >= min_price)
        if max_price is not None:
            base_query = base_query.filter(PharmacyProduct.price <= max_price)
        
        # Sorting
        if sort_by == 'price_asc':
            base_query = base_query.order_by(PharmacyProduct.price.asc())
        elif sort_by == 'price_desc':
            base_query = base_query.order_by(PharmacyProduct.price.desc())
        elif sort_by == 'name':
            base_query = base_query.order_by(Product.product_name.asc())
        else:  # relevance (default)
            if query:
                # Simple relevance scoring based on exact matches
                base_query = base_query.order_by(
                    func.case(
                        (Product.product_name.ilike(f'{query}%'), 1),
                        (Product.generic_name.ilike(f'{query}%'), 2),
                        (Product.brand_name.ilike(f'{query}%'), 3),
                        else_=4
                    ),
                    Product.product_name.asc()
                )
            else:
                base_query = base_query.order_by(Product.product_name.asc())
        
        # Paginate
        pagination = base_query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format results
        results = []
        for pharmacy_product, product, pharmacy in pagination.items:
            result = {
                'pharmacy_product': pharmacy_product.to_dict(),
                'product': product.to_dict(),
                'pharmacy': {
                    'id': pharmacy.id,
                    'pharmacy_name': pharmacy.pharmacy_name,
                    'pharmacy_name_ar': pharmacy.pharmacy_name_ar,
                    'district': pharmacy.district,
                    'rating_average': float(pharmacy.rating_average) if pharmacy.rating_average else 0.0,
                    'phone_number': pharmacy.phone_number
                }
            }
            results.append(result)
        
        return jsonify({
            'results': results,
            'pagination': {
                'page': pagination.page,
                'pages': pagination.pages,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            },
            'filters': {
                'query': query,
                'category_id': category_id,
                'district': district,
                'min_price': min_price,
                'max_price': max_price,
                'sort_by': sort_by
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Search products error: {str(e)}")
        return jsonify({'error': 'Failed to search products'}), 500

@search_bp.route('/pharmacies', methods=['GET'])
def search_pharmacies():
    """Search pharmacies by location and filters"""
    try:
        # Get query parameters
        district = request.args.get('district')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 10, type=float)  # km
        min_rating = request.args.get('min_rating', type=float)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Build query
        query = Pharmacy.query.filter(
            and_(
                Pharmacy.is_active == True,
                Pharmacy.is_verified == True
            )
        )
        
        # District filter
        if district:
            query = query.filter(Pharmacy.district.ilike(f'%{district}%'))
        
        # Rating filter
        if min_rating is not None:
            query = query.filter(Pharmacy.rating_average >= min_rating)
        
        # Location-based filtering (simplified - in production, use PostGIS)
        if latitude and longitude:
            # Simple bounding box filter (not accurate for large distances)
            lat_delta = radius / 111.0  # Approximate km to degrees
            lng_delta = radius / (111.0 * func.cos(func.radians(latitude)))
            
            query = query.filter(
                and_(
                    Pharmacy.latitude.between(latitude - lat_delta, latitude + lat_delta),
                    Pharmacy.longitude.between(longitude - lng_delta, longitude + lng_delta)
                )
            )
        
        # Order by rating
        query = query.order_by(Pharmacy.rating_average.desc(), Pharmacy.pharmacy_name.asc())
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format results
        pharmacies = []
        for pharmacy in pagination.items:
            pharmacy_data = pharmacy.to_dict()
            
            # Calculate distance if coordinates provided
            if latitude and longitude and pharmacy.latitude and pharmacy.longitude:
                # Simple distance calculation (not accurate for large distances)
                import math
                lat1, lon1 = math.radians(latitude), math.radians(longitude)
                lat2, lon2 = math.radians(float(pharmacy.latitude)), math.radians(float(pharmacy.longitude))
                
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                distance = 6371 * c  # Earth radius in km
                
                pharmacy_data['distance_km'] = round(distance, 2)
            
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
        current_app.logger.error(f"Search pharmacies error: {str(e)}")
        return jsonify({'error': 'Failed to search pharmacies'}), 500

@search_bp.route('/suggestions', methods=['GET'])
def get_search_suggestions():
    """Get search suggestions for autocomplete"""
    try:
        query = request.args.get('query', '').strip()
        limit = min(request.args.get('limit', 10, type=int), 20)
        
        if not query or len(query) < 2:
            return jsonify({'suggestions': []}), 200
        
        # Search in product names
        suggestions = []
        
        # Product name suggestions
        products = Product.query.filter(
            and_(
                Product.is_active == True,
                or_(
                    Product.product_name.ilike(f'{query}%'),
                    Product.product_name_ar.ilike(f'{query}%'),
                    Product.generic_name.ilike(f'{query}%'),
                    Product.brand_name.ilike(f'{query}%')
                )
            )
        ).limit(limit).all()
        
        for product in products:
            suggestions.append({
                'type': 'product',
                'text': product.product_name,
                'text_ar': product.product_name_ar,
                'id': product.id
            })
        
        # Remove duplicates and limit results
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            key = suggestion['text'].lower()
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(suggestion)
                if len(unique_suggestions) >= limit:
                    break
        
        return jsonify({
            'suggestions': unique_suggestions
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get search suggestions error: {str(e)}")
        return jsonify({'error': 'Failed to get search suggestions'}), 500

