from flask import Flask, request, jsonify, session, send_file, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask.views import MethodView
from datetime import datetime, timedelta
import os
import uuid
from flask_cors import CORS
from flask_migrate import Migrate
import os 
from werkzeug.utils import secure_filename



app = Flask(__name__, template_folder='Templates')
CORS(app)

app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///property_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

db = SQLAlchemy(app)
migrate = Migrate(app, db)
# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_dates(start_date, end_date):
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        return start < end
    except ValueError:
        return False

# Models
class User(db.Model):
    __tablename__ = 'users'
    
    user_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    properties = db.relationship('Property', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @classmethod
    def create(cls, full_name, email, password, phone_number):
        user = cls(
            full_name=full_name,
            email=email,
            phone_number=phone_number
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

class Property(db.Model):
    __tablename__ = 'properties'
    
    property_id = db.Column(db.String(20), primary_key=True, default=lambda: str(uuid.uuid4())[:20])
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    property_type = db.Column(db.String(50), nullable=False)
    street_name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    building_details = db.Column(db.Text)
    size_sqft = db.Column(db.Float, nullable=False)
    bedrooms = db.Column(db.Integer, nullable=False)
    occupancy_status = db.Column(db.String(20), default='vacant')
    current_occupancy = db.relationship('Occupancy', backref='property', uselist=False)
    documents = db.relationship('Document', backref='property', lazy=True)
    notifications = db.relationship('Notification', backref='property', lazy=True)
    rent_per_month = db.Column(db.Float, nullable=False)
    units = db.Column(db.Integer, nullable=False)
    
    def add_occupancy(self, tenant_data):
        if self.occupancy_status == 'occupied':
            raise ValueError("Property is already occupied")
        
        occupancy = Occupancy(
            property_id=self.property_id,
            tenant_name=tenant_data['tenant_name'],
            tenant_phone=tenant_data['tenant_phone'],
            tenant_email=tenant_data['tenant_email'],
            lease_start_date=tenant_data['lease_start_date'],
            lease_end_date=tenant_data['lease_end_date'],
            total_rent=tenant_data['total_rent']
        )
        self.occupancy_status = 'occupied'
        db.session.add(occupancy)
        db.session.commit()
        return occupancy

    def get_income_summary(self):
        if not self.current_occupancy:
            return {
                'total_rent': 0,
                'total_paid': 0,
                'total_due': 0,
                'payment_percentage': 0
            }
            
        total_paid = sum(p.amount for p in self.current_occupancy.payments if p.status == 'paid')
        total_due = sum(p.amount for p in self.current_occupancy.payments if p.status == 'due')
        return {
            'total_rent': self.current_occupancy.total_rent,
            'total_paid': total_paid,
            'total_due': total_due,
            'payment_percentage': (total_paid / self.current_occupancy.total_rent * 100)
        }

class Occupancy(db.Model):
    __tablename__ = 'occupancy'
    
    occupancy_id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.String(20), db.ForeignKey('properties.property_id'))
    tenant_name = db.Column(db.String(100), nullable=False)
    tenant_phone = db.Column(db.String(20))
    tenant_email = db.Column(db.String(120))
    lease_start_date = db.Column(db.Date, nullable=False)
    lease_end_date = db.Column(db.Date, nullable=False)
    total_rent = db.Column(db.Float, nullable=False)
    payments = db.relationship('Payment', backref='occupancy', lazy=True)

    def generate_payment_schedule(self, number_of_payments):
        payment_amount = self.total_rent / number_of_payments
        start_date = self.lease_start_date
        
        for i in range(number_of_payments):
            due_date = start_date + timedelta(days=(30 * i))
            payment = Payment(
                occupancy_id=self.occupancy_id,
                amount=payment_amount,
                due_date=due_date,
                status='due'
            )
            db.session.add(payment)
        db.session.commit()

    def to_dict(self):
        return {
            'tenant_name': self.tenant_name,
            'tenant_phone': self.tenant_phone,
            'tenant_email': self.tenant_email,
            'lease_start_date': self.lease_start_date.strftime('%Y-%m-%d'),
            'lease_end_date': self.lease_end_date.strftime('%Y-%m-%d'),
            'total_rent': self.total_rent
        }

class Payment(db.Model):
    __tablename__ = 'payments'
    
    payment_id = db.Column(db.Integer, primary_key=True)
    occupancy_id = db.Column(db.Integer, db.ForeignKey('occupancy.occupancy_id'))
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='due')

    def mark_as_paid(self):
        self.status = 'paid'
        db.session.commit()

class Document(db.Model):
    __tablename__ = 'documents'
    
    document_id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.String(20), db.ForeignKey('properties.property_id'))
    title = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    upload_date = db.Column(db.Date, default=datetime.utcnow)

    def to_dict(self):
        return {
            'document_id': self.document_id,
            'title': self.title,
            'upload_date': self.upload_date.strftime('%Y-%m-%d')
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    notification_id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.String(20), db.ForeignKey('properties.property_id'))
    notification_type = db.Column(db.String(50), nullable=False)  # 'lease_renewal' or 'payment'
    notification_period = db.Column(db.Integer, nullable=False)  # 7, 15, or 30 days
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'notification_id': self.notification_id,
            'notification_type': self.notification_type,
            'notification_period': self.notification_period,
            'is_active': self.is_active
        }

class Dashboard(db.Model):
    __tablename__ = 'dashboard'

    id = db.Column(db.Integer, primary_key=True)
    total_properties = db.Column(db.Integer, nullable=False)
    total_tenants = db.Column(db.Integer, nullable=False)
    total_income = db.Column(db.Float, nullable=False)
    vacant_properties = db.Column(db.Integer, nullable=False)

    @classmethod
    def get_dashboard_data(cls):
        total_properties = Property.query.count()
        total_tenants = Tenant.query.count()
        total_income = sum(payment.amount for payment in Payment.query.filter_by(status='paid'))
        vacant_properties = Property.query.filter_by(occupancy_status='vacant').count()

        return cls(
            total_properties=total_properties,
            total_tenants=total_tenants,
            total_income=total_income,
            vacant_properties=vacant_properties
        )



# Views
class AuthenticatedMethodView(MethodView):
    """Base class for views that require authentication"""
    
    def dispatch_request(self, *args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return super().dispatch_request(*args, **kwargs)

class UserView(MethodView):
    def post(self):
        """Handle user signup"""
        data = request.json
        if not all(k in data for k in ['full_name', 'email', 'password', 'phone_number']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        try:
            user = User.create(
                full_name=data['full_name'],
                email=data['email'],
                password=data['password'],
                phone_number=data['phone_number']
            )
            return jsonify({'message': 'User created successfully'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

class LoginView(MethodView):
    def post(self):
        """Handle user login"""
        data = request.json
        

        if not all(k in data for k in ['email', 'password']):
            return jsonify({'error': 'Missing credentials'}), 400

        user = User.query.filter_by(email=data['email']).first()
        if user and user.check_password(data['password']):
            session['user_id'] = user.user_id
            return jsonify({'message': 'Login successful'}), 200
        return jsonify({'error': 'Invalid credentials'}), 401

# probably wrong:
# class DashboardView(MethodView):
#     def get(self):
#         """Get dashboard summary"""
#         # Fetch the logged-in user
#         user = User.query.get(session['user_id'])
        
#         # Fetch all properties for the user
#         properties = Property.query.filter_by(user_id=user.user_id).all()

#         # Calculate dashboard summary
#         summary = {
#             'properties': {
#                 'total': len(properties),
#                 'vacant': sum(1 for p in properties if p.occupancy_status == 'vacant'),
#                 'occupied': sum(1 for p in properties if p.occupancy_status == 'occupied')
#             },
#             'finances': {
#                 'total_income': sum(p.get_income_summary()['total_paid'] for p in properties if p.current_occupancy),
#                 'total_pending': sum(p.get_income_summary()['total_due'] for p in properties if p.current_occupancy),
#             },
#             'upcoming_renewals': sum(
#                 1 for p in properties 
#                 if p.current_occupancy and 
#                 (p.current_occupancy.lease_end_date - datetime.now().date()).days <= 30
#             )
#         }

#         return jsonify(summary), 200   



class PasswordResetView(AuthenticatedMethodView):
    def post(self):
        """Handle password reset"""
        data = request.json
        if not all(k in data for k in ['old_password', 'new_password']):
            return jsonify({'error': 'Missing required fields'}), 400

        user = User.query.get(session['user_id'])
        if not user.check_password(data['old_password']):
            return jsonify({'error': 'Invalid old password'}), 400

        try:
            user.set_password(data['new_password'])
            db.session.commit()
            return jsonify({'message': 'Password updated successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

class PropertyView(AuthenticatedMethodView):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS


    def post(self):
        """Add a new property"""
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401

        data = request.form  # Use form data to handle both JSON and file inputs
        image_file = request.files.get('image')

        # Check if image is provided and valid
        image_filename = None
        if image_file and self.allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        # Ensure required fields are present
        required_fields = ['property_type', 'street_name', 'city', 'size_sqft', 'bedrooms', 'units', 'rent_per_month', 'occupancy_status']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f"Missing fields: {', '.join(missing_fields)}"}), 400

        try:
            # Create the new property
            new_property = Property(
                user_id=session['user_id'],
                property_type=data['property_type'],
                street_name=data['street_name'],
                city=data['city'],
                building_details=data.get('building_details'),  # Optional
                size_sqft=float(data['size_sqft']),
                bedrooms=int(data['bedrooms']),
                units=int(data['units']),
                rent_per_month=float(data['rent_per_month']),
                occupancy_status=data['occupancy_status'],
                image=image_filename  # Save the image filename in the database
            )

            db.session.add(new_property)
            db.session.commit()

            return jsonify({'message': 'Property added successfully', 'property_id': new_property.property_id}), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f"Failed to add property: {str(e)}"}), 500

    def get(self):
        """Get all properties for the logged-in user"""
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401

        # Fetch properties belonging to the logged-in user
        user_id = session['user_id']
        properties = Property.query.filter_by(user_id=user_id).all()

        if not properties:
            print('properties does not exist')
            return render_template('properties.html', properties=[])

        # Convert properties to dictionaries
        properties_data = [
            {
                'property_id': p.property_id,
                'property_type': p.property_type,
                'street_name': p.street_name,
                'city': p.city,
                'size_sqft': p.size_sqft,
                'bedrooms': p.bedrooms,
                'rent_per_month': p.rent_per_month,
                'units': p.units,
                'occupancy_status': p.occupancy_status,
                'building_details': p.building_details,
                # Use default image if no image is provided
                'image': 'default.jpg'  # Replace this with p.image if image uploads are implemented
            }
            for p in properties
        ]
        return jsonify(properties_data), 200
        # return render_template('properties.html', properties=properties_data)   


class PropertyDetailView(AuthenticatedMethodView):
    def get(self, property_id):
        """Get details for a specific property"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()
        
        return jsonify({
            'property': {
                'property_id': property.property_id,
                'property_type': property.property_type,
                'street_name': property.street_name,
                'city': property.city,
                'building_details': property.building_details,
                'size_sqft': property.size_sqft,
                'bedrooms': property.bedrooms,
                'occupancy_status': property.occupancy_status
            },
            'occupancy': property.current_occupancy.to_dict() if property.current_occupancy else None,
            'income_summary': property.get_income_summary()
        }), 200

    def put(self, property_id):
        """Update a property"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()

        data = request.json
        try:
            for key, value in data.items():
                if hasattr(property, key):
                    setattr(property, key, value)
            db.session.commit()
            return jsonify({'message': 'Property updated successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    def delete(self, property_id):
        """Delete a property"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()

        if property.current_occupancy:
            return jsonify({
                'warning': 'Property has active occupancy. Confirm deletion?',
                'requires_confirmation': True
            }), 200

        try:
            db.session.delete(property)
            db.session.commit()
            return jsonify({'message': 'Property deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

class OccupancyView(AuthenticatedMethodView):
    def post(self, property_id):
        """Add new occupancy to a property"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()

        data = request.json
        if not validate_dates(data['lease_start_date'], data['lease_end_date']):
            return jsonify({'error': 'Invalid date range'}), 400

        try:
            occupancy = property.add_occupancy(data)
            occupancy.generate_payment_schedule(data['number_of_payments'])
            return jsonify({'message': 'Occupancy added successfully'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    def put(self, property_id):
        """Update occupancy details"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()

        if not property.current_occupancy:
            return jsonify({'error': 'No active occupancy found'}), 404

        data = request.json
        try:
            occupancy = property.current_occupancy
            for key, value in data.items():
                if hasattr(occupancy, key):
                    setattr(occupancy, key, value)
            db.session.commit()
            return jsonify({'message': 'Occupancy updated successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    def delete(self, property_id):
        """End occupancy"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()

        if not property.current_occupancy:
            return jsonify({'error': 'No active occupancy found'}), 404

        try:
            db.session.delete(property.current_occupancy)
            property.occupancy_status = 'vacant'
            db.session.commit()
            return jsonify({'message': 'Occupancy ended successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

class DocumentView(AuthenticatedMethodView):
    def get(self, property_id):
        """Get all documents for a property"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()

        return jsonify([doc.to_dict() for doc in property.documents]), 200

    def post(self, property_id):
        """Upload a new document"""
        property = Property.query.filter_by(
            property_id=property_id, 
            user_id=session['user_id']
        ).first_or_404()

        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file'}), 400

        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            document = Document(
                property_id=property_id,
                title=request.form.get('title', filename),
                file_path=file_path
            )
            db.session.add(document)
            db.session.commit()
            return jsonify({'message': 'Document uploaded successfully'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

class DocumentDetailView(AuthenticatedMethodView):
    def get(self, document_id):
        """Download a document"""
        document = Document.query.join(Property).filter(
            Document.document_id == document_id,
            Property.user_id == session['user_id']
        ).first_or_404()
        
        return send_file(document.file_path, as_attachment=True)

    def delete(self, document_id):
        """Delete a document"""
        document = Document.query.join(Property).filter(
            Document.document_id == document_id,
            Property.user_id == session['user_id']
        ).first_or_404()

        try:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
            db.session.delete(document)
            db.session.commit()
            return jsonify({'message': 'Document deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

class IncomeView(AuthenticatedMethodView):
    def get(self, property_id):
        """Track income for a property"""
        property = Property.query.filter_by(
            property_id=property_id,
            user_id=session['user_id']
        ).first_or_404()
        
        return jsonify(property.get_income_summary()), 200

class NotificationView(AuthenticatedMethodView):
    def post(self, property_id):
        """Set notification preferences"""
        property = Property.query.filter_by(
            property_id=property_id,
            user_id=session['user_id']
        ).first_or_404()

        data = request.json
        if not all(k in data for k in ['notification_type', 'notification_period']):
            return jsonify({'error': 'Missing required fields'}), 400
            
        if data['notification_period'] not in [7, 15, 30]:
            return jsonify({'error': 'Invalid notification period'}), 400
            
        if data['notification_type'] not in ['lease_renewal', 'payment']:
            return jsonify({'error': 'Invalid notification type'}), 400

        try:
            existing = Notification.query.filter_by(
                property_id=property_id,
                notification_type=data['notification_type']
            ).first()
            
            if existing:
                existing.notification_period = data['notification_period']
                existing.is_active = True
            else:
                notification = Notification(
                    property_id=property_id,
                    notification_type=data['notification_type'],
                    notification_period=data['notification_period']
                )
                db.session.add(notification)
                
            db.session.commit()
            return jsonify({'message': 'Notification preferences saved'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

    def get(self, property_id):
        """Get notification settings for a property"""
        property = Property.query.filter_by(
            property_id=property_id,
            user_id=session['user_id']
        ).first_or_404()

        notifications = Notification.query.filter_by(
            property_id=property_id,
            is_active=True
        ).all()

        return jsonify([n.to_dict() for n in notifications]), 200

    def delete(self, property_id):
        """Disable notifications for a property"""
        property = Property.query.filter_by(
            property_id=property_id,
            user_id=session['user_id']
        ).first_or_404()

        data = request.json
        if 'notification_type' not in data:
            return jsonify({'error': 'Missing notification type'}), 400

        try:
            notification = Notification.query.filter_by(
                property_id=property_id,
                notification_type=data['notification_type']
            ).first_or_404()
            
            notification.is_active = False
            db.session.commit()
            return jsonify({'message': 'Notification disabled successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

class NotificationCheckView(AuthenticatedMethodView):
    def get(self):
        """Check all active notifications"""
        current_date = datetime.now().date()
        
        notifications = (
            Notification.query
            .join(Property)
            .filter(
                Property.user_id == session['user_id'],
                Notification.is_active == True
            )
            .all()
        )

        lease_notifications = []
        payment_notifications = []

        for notification in notifications:
            property = notification.property
            if not property.current_occupancy:
                continue

            if notification.notification_type == 'lease_renewal':
                days_until_end = (property.current_occupancy.lease_end_date - current_date).days
                if 0 <= days_until_end <= notification.notification_period:
                    lease_notifications.append({
                        'property_id': property.property_id,
                        'street_name': property.street_name,
                        'lease_end_date': property.current_occupancy.lease_end_date.strftime('%Y-%m-%d'),
                        'days_remaining': days_until_end
                    })

            elif notification.notification_type == 'payment':
                for payment in property.current_occupancy.payments:
                    if payment.status == 'due':
                        days_until_due = (payment.due_date - current_date).days
                        if 0 <= days_until_due <= notification.notification_period:
                            payment_notifications.append({
                                'property_id': property.property_id,
                                'street_name': property.street_name,
                                'amount': payment.amount,
                                'due_date': payment.due_date.strftime('%Y-%m-%d'),
                                'days_until_due': days_until_due
                            })

        return jsonify({
            'lease_renewals': lease_notifications,
            'payment_dues': payment_notifications
        }), 200

class DashboardView(AuthenticatedMethodView):
    def get(self):
        """Get dashboard summary"""
        user = User.query.get(session['user_id'])
        properties = Property.query.filter_by(user_id=user.user_id).all()
        
        summary = {
            'properties': {
                'total': len(properties),
                'vacant': sum(1 for p in properties if p.occupancy_status == 'vacant'),
                'occupied': sum(1 for p in properties if p.occupancy_status == 'occupied')
            },
            'finances': {
                'total_income': sum(p.get_income_summary()['total_paid'] for p in properties if p.current_occupancy),
                'total_pending': sum(p.get_income_summary()['total_due'] for p in properties if p.current_occupancy),
            },
            'upcoming_renewals': sum(
                1 for p in properties 
                if p.current_occupancy and 
                (p.current_occupancy.lease_end_date - datetime.now().date()).days <= 30
            )
        }
        return jsonify(summary), 200

class PropertySummaryView(AuthenticatedMethodView):
    def get(self, property_id):
        """Get property summary"""
        property = Property.query.filter_by(
            property_id=property_id,
            user_id=session['user_id']
        ).first_or_404()
        
        return jsonify({
            'property': {
                'property_id': property.property_id,
                'property_type': property.property_type,
                'street_name': property.street_name,
                'city': property.city,
                'building_details': property.building_details,
                'size_sqft': property.size_sqft,
                'bedrooms': property.bedrooms,
                'occupancy_status': property.occupancy_status
            },
            'occupancy': property.current_occupancy.to_dict() if property.current_occupancy else None,
            'income_summary': property.get_income_summary(),
            'document_count': len(property.documents)
        }), 200

class PropertyOverviewView(AuthenticatedMethodView):
    def get(self):
        """Get properties overview statistics for the logged-in user"""
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401

        user_id = session['user_id']
        
        # Total properties
        total_properties = Property.query.filter_by(user_id=user_id).count()

        # Occupied properties
        occupied_properties = Property.query.filter_by(user_id=user_id, occupancy_status='occupied').count()

        # Vacant properties
        vacant_properties = Property.query.filter_by(user_id=user_id, occupancy_status='vacant').count()

        # Return the statistics as JSON
        return jsonify({
            'total_properties': total_properties,
            'occupied_properties': occupied_properties,
            'vacant_properties': vacant_properties
        })


def register_routes(app):
    """Register all routes with the Flask app"""
    @app.route('/api/signup')
    def signup_page3():
        return render_template('/signup.html')
    
    @app.route('/signup.html')
    def signup_page():
        return render_template('/signup.html')
    
    @app.route('/signup')
    def signup_page2():
        return render_template('/signup.html')

    @app.route('/login.html')
    def login_page():
        return render_template('/login.html')
    
    @app.route('/login')
    def login_page2():
        return render_template('/login.html')
    
    @app.route('/')
    def home():
        return render_template('/landing.html')
    
    @app.route('/landing.html')
    def home2():
        return render_template('/landing.html')

    # User routes

    app.add_url_rule('/login', view_func=LoginView.as_view('login'))
    app.add_url_rule('/api/signup', view_func=UserView.as_view('user'))
    
    @app.route('/dashboard.html')
    def dashboard():
            return render_template('dashboard.html')
    
    @app.route('/dashboard')
    def dashboard2():
            return render_template('dashboard.html')
    
    # app.add_url_rule('/dashboard', view_func=DashboardView.as_view('dashboard'))

    

    # Property routes
    @app.route('/properties')
    def properties_page3():
        # properties = Property.query.all()
        return render_template('properties.html')
    


    @app.route('/properties.html')
    def properties_page2():
        # properties = Property.query.all()
        return render_template('properties.html')
    


    app.add_url_rule('/api/properties', view_func=PropertyView.as_view('properties'))
    app.add_url_rule('/api/properties/overview', view_func=PropertyOverviewView.as_view('properties_overview'))


    # Occupancy routes
    @app.route('/occupants')
    def occupants_page():
        return render_template('occupants.html')
    
    app.add_url_rule(
        '/api/properties/<property_id>/occupancy', 
        view_func=OccupancyView.as_view('occupancy')
    )
    
    # Document routes
    @app.route('/documents')
    def documents_page():
        return render_template('documents.html')
    
    app.add_url_rule(
        '/api/properties/<property_id>/documents', 
        view_func=DocumentView.as_view('documents')
    )
    app.add_url_rule(
        '/api/documents/<document_id>',
        view_func=DocumentDetailView.as_view('document_detail')
    )
    
    # Income route
    @app.route('/income')
    def income_page():
        return render_template('income.html')
    
    app.add_url_rule(
        '/api/properties/<property_id>/income',
        view_func=IncomeView.as_view('income')
    )
    
    # # Notification routes
    # app.add_url_rule(
    #     '/api/properties/<property_id>/notifications',
    #     view_func=NotificationView.as_view('notifications')
    # )
    # app.add_url_rule(
    #     '/api/notifications/check',
    #     view_func=NotificationCheckView.as_view('check_notifications')
    # )
    
    # # Summary routes
    # app.add_url_rule(
    #     '/api/properties/<property_id>/summary',
    #     view_func=PropertySummaryView.as_view('property_summary')
    # )
    # app.add_url_rule(
    #     '/api/dashboard',
    #     view_func=DashboardView.as_view('dashboard')
    # )

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Initialize the application
def init_app():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    init_app()
    register_routes(app)
    app.run(debug=True)

