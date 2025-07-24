#!/usr/bin/env python3
"""
Database Schema Fix Script for DawakSahl Backend

This script fixes the foreign key type mismatch issue by dropping and recreating
the database tables with the correct schema.

Usage:
    python fix_database_schema.py
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import create_app
from models.database import db

def fix_database_schema():
    """Fix the database schema by dropping and recreating tables"""
    
    print("🔧 Starting database schema fix...")
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        try:
            # Get the database engine
            engine = db.engine
            
            print("📋 Current database URL:", engine.url)
            
            # Drop all tables
            print("🗑️  Dropping all existing tables...")
            db.drop_all()
            print("✅ All tables dropped successfully")
            
            # Create all tables with correct schema
            print("🏗️  Creating tables with correct schema...")
            db.create_all()
            print("✅ All tables created successfully")
            
            # Verify the schema
            print("🔍 Verifying table creation...")
            with engine.connect() as conn:
                # Check if tables exist
                tables_query = text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name;
                """)
                
                result = conn.execute(tables_query)
                tables = [row[0] for row in result]
                
                print(f"📊 Created {len(tables)} tables:")
                for table in tables:
                    print(f"   - {table}")
                
                # Check user_addresses foreign key
                fk_query = text("""
                    SELECT 
                        tc.constraint_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name,
                        pgc1.data_type AS local_type,
                        pgc2.data_type AS foreign_type
                    FROM 
                        information_schema.table_constraints AS tc 
                        JOIN information_schema.key_column_usage AS kcu
                          ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage AS ccu
                          ON ccu.constraint_name = tc.constraint_name
                        JOIN information_schema.columns AS pgc1
                          ON pgc1.table_name = tc.table_name AND pgc1.column_name = kcu.column_name
                        JOIN information_schema.columns AS pgc2
                          ON pgc2.table_name = ccu.table_name AND pgc2.column_name = ccu.column_name
                    WHERE 
                        tc.constraint_type = 'FOREIGN KEY' 
                        AND tc.table_name = 'user_addresses'
                        AND kcu.column_name = 'user_id';
                """)
                
                result = conn.execute(fk_query)
                fk_info = result.fetchone()
                
                if fk_info:
                    print(f"🔗 Foreign key verification:")
                    print(f"   - Local column type: {fk_info[4]}")
                    print(f"   - Foreign column type: {fk_info[5]}")
                    
                    if fk_info[4] == fk_info[5]:
                        print("✅ Foreign key types match correctly!")
                    else:
                        print("❌ Foreign key types still don't match!")
                        return False
                else:
                    print("⚠️  Could not verify foreign key constraint")
            
            print("🎉 Database schema fix completed successfully!")
            return True
            
        except SQLAlchemyError as e:
            print(f"❌ Database error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

def create_sample_data():
    """Create sample data for testing"""
    
    print("📝 Creating sample data...")
    
    try:
        from models.user import User, UserType
        from models.admin import District
        
        # Create districts
        districts_data = [
            {'name': 'Al Mudhaffar', 'name_ar': 'المظفر'},
            {'name': 'Salh', 'name_ar': 'صالح'},
            {'name': 'Al Qahirah', 'name_ar': 'القاهرة'},
            {'name': 'Jamal', 'name_ar': 'جمال'},
            {'name': 'Al Taaiziyah', 'name_ar': 'التعزية'},
            {'name': 'Sabir Al Mawadim', 'name_ar': 'صبر الموادم'},
            {'name': 'Sama', 'name_ar': 'سامع'},
            {'name': 'Ash Shamayatayn', 'name_ar': 'الشمايتين'},
            {'name': 'Dimnat Khadir', 'name_ar': 'دمنة خدير'},
            {'name': 'Hayfan', 'name_ar': 'حيفان'}
        ]
        
        for district_data in districts_data:
            district = District(**district_data)
            db.session.add(district)
        
        # Create a test admin user
        admin_user = User(
            email='admin@dawaksahl.com',
            phone_number='+967733733870',
            first_name='Admin',
            last_name='DawakSahl',
            user_type=UserType.ADMIN,
            is_verified=True,
            is_active=True
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        
        # Create a test customer
        customer_user = User(
            email='customer@example.com',
            phone_number='+967733733871',
            first_name='Ahmed',
            last_name='Al-Yemeni',
            user_type=UserType.CUSTOMER,
            is_verified=True,
            is_active=True
        )
        customer_user.set_password('customer123')
        db.session.add(customer_user)
        
        db.session.commit()
        print("✅ Sample data created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        db.session.rollback()

if __name__ == '__main__':
    print("🚀 DawakSahl Database Schema Fix")
    print("=" * 50)
    
    success = fix_database_schema()
    
    if success:
        create_sample_data()
        print("\n🎉 Database is ready for use!")
        print("\nTest credentials:")
        print("Admin: admin@dawaksahl.com / admin123")
        print("Customer: customer@example.com / customer123")
    else:
        print("\n❌ Database fix failed. Please check the errors above.")
        sys.exit(1)

