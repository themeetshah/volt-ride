from flask import Flask, request, jsonify, render_template, redirect, flash, url_for, session
import mysql.connector
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import base64
from werkzeug.utils import secure_filename
import firebase_admin
from firebase_admin import credentials, firestore, storage
#location
import time
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.secret_key = os.getenv('SECRET_KEY')  # Make sure to set a secret key

app.config['UPLOAD_FOLDER'] = 'uploads'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# OTP storage
otp_storage = {}

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_config.json")
    firebase_admin.initialize_app(cred, {
    'storageBucket': 'your-firebase-app-id.appspot.com',  # Firebase storage bucket
})

# MySQL Database Configuration
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="voltride"
)
cursor = db.cursor(dictionary=True)

# Generate OTP
def generate_otp():
    return str(random.randint(100000, 999999))

# Send OTP via Email using App Password
def send_otp_via_email(email, otp, name):
    try:
        sender_email = os.getenv('EMAIL_SENDER')
        app_password = os.getenv('EMAIL_PASSWORD')
        subject = "Volt Ride OTP"
             # HTML message body with OTP styled in bold and custom color
        # HTML message body with OTP styled in bold and custom color
        message_body = f"""
            <html>
            <head>
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                    }}
                    .otp {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #000000;
                    }}
                    .content {{
                        word-wrap: break-word;
                        white-space: normal;
                    }}
                </style>
            </head>
            <body>
                <p>Hello {name},</p>

                <p>Your OTP (One-Time Password) for Volt Ride is: <span class="otp">{otp}</span>. This code is required to complete your authentication process.</p>

                <p class="content">If you did not request this OTP, please disregard this email.</p>

                <p class="content">Thank you for choosing Volt Ride!</p>

                <p class="content">Regards,<br>Volt Ride Team</p>
            </body>
            </html>
        """


        # Create Email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(message_body, 'html'))

        # Send Email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, email, msg.as_string())
        
        print(f"OTP {otp} sent to {email}")
        return True
    except Exception as e:
        print(f"Failed to send OTP: {e}")
        return False

# Render Login Page
@app.route('/')
def index():
    return render_template('index.html')

# Send OTP Endpoint
@app.route('/send_otp', methods=['POST'])
def send_otp():
    name = request.form.get('signUpName')
    email = request.form.get('signUpNum')

    otp = generate_otp()
    otp_storage[email] = otp

    if send_otp_via_email(email, otp, name):
        return render_template('otp_input.html', email=email)
    else:
        return render_template('error.html', message="Failed to send OTP")
    
# OTP Input Page
@app.route('/otp_input/<email>', methods=['GET', 'POST'])
def otp_input(email):
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        if otp_storage.get(email) == entered_otp:
            return render_template('register.html', email=email)
        else:
            return render_template('login.html', message="Incorrect OTP, please try again.")
        
    return render_template('otp_input.html', email=email)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/register/<email>', methods=['GET', 'POST'])
def register(email):
    if request.method == 'POST':
        # Retrieve form data
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        mobile = request.form.get('mobile')
        password = request.form.get('passwordHash')
        confirm_password = request.form.get('confirmPassword')
        licence_number = request.form.get('licenceNumber')
        file = request.files.get('licencePhoto')

        # Validate file upload
        if not file or file.filename == '':
            flash("No selected file", 'danger')
            return render_template('register.html', email=email)
        
        if not allowed_file(file.filename):
            flash("Invalid file type. Only images are allowed.", 'danger')
            return render_template('register.html', email=email)

        # Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match!", 'danger')
            return render_template('register.html', email=email)

        # Secure and save the uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Convert to Base64
        with open(file_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')

        try:
            print(
                first_name, 
                last_name,
                mobile,
                password,
                licence_number,
                encoded_string
            )
            # Insert data into the database
            cursor.execute("""
                INSERT INTO user (`first-name`, `last-name`, email, mobile, password, `licence-photo`, `licence-number`, approval)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (first_name, last_name, email, mobile, password, encoded_string, licence_number))
            
            db.commit()

            flash('Registration successful! Please wait for approval.', 'success')
            print('Registration successful! Please wait for approval.', 'success')
            return redirect(url_for("login"))
        
        except mysql.connector.Error as err:
            print("MySQL Error:", err)
            flash(f"MySQL Error: {err}", 'danger')
            return render_template('register.html', email=email)
        
        except Exception as e:
            print("General Error:", e)
            flash(f"An unexpected error occurred: {e}", 'danger')
            return render_template('register.html', email=email)

    return render_template("register.html", email=email)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if session['role']=='master':
        print(session['email_id'])
        # Fetch admin details from MySQL
        cursor.execute("SELECT `station-id` FROM stations WHERE `master-id` =(Select `user-id` from user where email = %s)", (session['email_id'],))
        station = cursor.fetchone()
        session['station-id']=station['station-id']
        return render_template('admin_dashboard.html')
    elif session['role']=='user':
        return render_template('user_dashboard.html')

@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template('about_us.html')

# @app.route('/vehicle', methods=['GET', 'POST'])
# def vehicle():
#     return render_template('vehicle_details.html')

# @app.route('/station', methods=['GET', 'POST'])
# def station():
#     return render_template('station_details.html')


@app.route("/logout")
def logout():
    session.pop("email_id", None)
    session.pop("role", None)
    return redirect(url_for("index"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        # Fetch admin details from MySQL
        cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        print(email, password)
        
        if user and user["password"] == password:  # Validate password without hashing
            session["email_id"] = user["email"]
            session["role"] = user["role"]
            role = user["role"]
            if role:
                if role == 'master':
                    return render_template('admin_dashboard.html')
                elif role == 'user':
                    return render_template('user_dashboard.html')
        else:
            print(user)
            return render_template('error.html', message="Invalid email or password")
    return render_template('login.html')

@app.route('/vehicle')
def vehicles():
    try:
        cursor.execute("""
            SELECT v.`v-id`, v.`name`, v.`reg-plate`, v.`status`, s.`name` as 'station_name'
            FROM vehicle v
            JOIN stations s ON v.`station-id` = s.`station-id`
        """)
        vehicles_data = cursor.fetchall()

        return render_template('vehicle_details.html', vehicles=vehicles_data)
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        flash("Failed to fetch vehicle data", 'danger')
        return render_template('vehicle_details.html', vehicles=[])

@app.route('/api/vehicles/<station_id>', methods=['GET'])
def get_vehicles(station_id):
    try:
        cursor.execute("""
            SELECT v.`v-id`, v.`name`, v.`reg-plate`, v.`battery`, v.`status`, s.`name` as 'station_name'
            FROM vehicle v
            JOIN stations s ON v.`station-id` = s.`station-id`
            WHERE s.`station-id` = %s
        """, (station_id,))
        vehicles_data = cursor.fetchall()
        return jsonify(vehicles_data)
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"error": "Failed to fetch vehicle data"}), 500

@app.route('/vehicle/edit/<int:vehicle_id>', methods=['GET', 'POST'])
def edit_vehicle(vehicle_id):
    try:
        cursor = db.cursor(dictionary=True)

        # Fetch vehicle data for pre-filling the form
        cursor.execute("SELECT * FROM vehicle WHERE `v-id` = %s", (vehicle_id,))
        vehicle = cursor.fetchone()

        if not vehicle:
            flash("Vehicle not found", 'danger')
            return redirect(url_for('vehicles'))

        # Fetch stations for dropdown
        cursor.execute("SELECT `station-id`, `name` FROM stations")
        stations = cursor.fetchall()

        if request.method == 'POST':
            reg_plate = request.form['reg_plate']
            name = request.form['name']
            battery = request.form['battery']
            station_id = request.form['station_id']
            status = request.form['status']

            # Update vehicle details
            cursor.execute("""
                UPDATE vehicle 
                SET `reg-plate`=%s, `name`=%s, `battery`=%s, `station-id`=%s, `status`=%s
                WHERE `v-id`=%s
            """, (reg_plate, name, battery, station_id, status, vehicle_id))

            db.commit()
            flash("Vehicle updated successfully", "success")
            return redirect(url_for('vehicles'))

        return render_template('edit_vehicle.html', vehicle=vehicle, stations=stations)

    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        flash("Failed to edit vehicle", 'danger')
        return redirect(url_for('vehicles'))

@app.route('/add-vehicle', methods=['GET', 'POST'])
def add_vehicle():
    if request.method == 'POST':
        reg_plate = request.form['reg_plate']
        name = request.form['name']
        battery = float(request.form['battery'])
        station_id = int(request.form['station_id'])
        status = request.form['status']

        # Insert into database
        query = "INSERT INTO vehicle (reg-plate, name, battery, station-id, status) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, (reg_plate, name, battery, station_id, status))
        db.commit()

        return redirect('/add-vehicle')

    return render_template('add_vehicle.html')

@app.route('/vehicle/delete/<int:vehicle_id>')
def delete_vehicle(vehicle_id):
    try:
        cursor = db.cursor()

        # Check if the vehicle exists
        cursor.execute("SELECT `v-id` FROM vehicle WHERE `v-id` = %s", (vehicle_id,))
        vehicle = cursor.fetchone()
        if not vehicle:
            flash("Vehicle not found", "danger")
            return redirect(url_for('vehicles'))

        # Perform deletion
        cursor.execute("DELETE FROM vehicle WHERE `v-id` = %s", (vehicle_id,))
        db.commit()
        cursor.execute("DELETE FROM charging_ports WHERE `vehicle-id` = %s", (vehicle_id,))
        db.commit()

        flash("Vehicle deleted successfully", "success")
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        flash("Failed to delete vehicle", 'danger')
    return redirect(url_for('vehicle'))

@app.route('/station')
def station_details():
    # Fetch Station Details
    cursor.execute("""
        SELECT stations.*, COUNT(*) AS total_vehicle
        FROM stations
        INNER JOIN charging_ports AS cp ON stations.`station-id` = cp.`station-id`
        WHERE stations.`station-id` = %s
    """, (session['station-id'],))
    station = cursor.fetchone()

    # Fetch Charging Port Details
    cursor.execute("""
        SELECT cp.`port-id`,
            cp.status,
            IF(cp.`vehicle-id` = 0, '-', cp.`vehicle-id`) AS `vehicle-id`,
            IF(cp.`battery` IS NULL, '-', v.battery) AS battery
        FROM charging_ports cp
        LEFT JOIN vehicle v ON cp.`vehicle-id` = v.`v-id`
        WHERE cp.`station-id` = %s;
    """, (session['station-id'],))
    ports = cursor.fetchall()

    return render_template('station_details.html', station=station, ports=ports)

@app.route('/profile')
def profile():
    
    email = session['email_id']
    # Get User Details
    cursor.execute("SELECT * FROM user WHERE `email` = %s", (email,))
    user = cursor.fetchone()

    if not user:
        return "User not found", 404

    # Get Ride History
    cursor.execute("SELECT * FROM ride WHERE `user-id` = (SELECT `user-id` from user WHERE `email` = %s)", (email,))
    rides = cursor.fetchone()

    return render_template('profile.html', user=user, rides=rides)



@app.route('/location')
def location():
    return render_template('location.html')

# Define geofence boundaries (example)
GEOFENCE_CENTER = (23.15462, 72.66685)  # Example center coordinates
GEOFENCE_RADIUS = 5000  # 5 km

# Store tracking info
user_tracking = {}

def is_outside_geofence(lat, lon):
    """Check if the user is outside geofence"""
    from geopy.distance import geodesic
    distance = geodesic((lat, lon), GEOFENCE_CENTER).km
    return distance > (GEOFENCE_RADIUS / 1000)  # Convert meters to km


@app.route('/track', methods=['POST'])
def track_location():
    """Track user location and apply penalty if needed"""
    data = request.json
    user_id = data['user_id']
    lat, lon = data['lat'], data['lon']
    
    if user_id not in user_tracking:
        user_tracking[user_id] = {
            'start_time': time.time(),
            'inside_geofence': True,
            'penalty_start': None,
            'distance': 0,
            'total_cost': 0,
            'cost_per_km': 1.50
        }
    
    tracking = user_tracking[user_id]
    
    # Check if user is outside the geofence
    if is_outside_geofence(lat, lon):
        if tracking['inside_geofence']:
            tracking['inside_geofence'] = False
            tracking['penalty_start'] = time.time()  # Start penalty timer
            return jsonify({"alert": "You have exited the geofence! Return within 10 minutes to avoid penalties."})

        # Check if 10 minutes have passed
        elif time.time() - tracking['penalty_start'] >= 600:  # 10 minutes = 600 seconds
            tracking['cost_per_km'] = 20  # Apply penalty
    else:
        if not tracking['inside_geofence']:
            tracking['inside_geofence'] = True
            tracking['penalty_start'] = None
            tracking['cost_per_km'] = 1.50  # Reset price

    # Update distance and cost
    if 'prev_lat' in tracking and 'prev_lon' in tracking:
        distance = get_distance(tracking['prev_lat'], tracking['prev_lon'], lat, lon)
        tracking['distance'] += distance
        tracking['total_cost'] += distance * tracking['cost_per_km']

    tracking['prev_lat'] = lat
    tracking['prev_lon'] = lon

    return jsonify({"status": "Tracking updated"})


def get_distance(lat1, lon1, lat2, lon2):
    from geopy.distance import geodesic
    return geodesic((lat1, lon1), (lat2, lon2)).km

import cv2
from pyzbar.pyzbar import decode

@app.route('/scan_qr_live')
def scan_qr_live():
    return render_template('scan_qr_live.html')

@app.route('/process_qr', methods=['POST'])
def process_qr():
    try:
        # Capture video from the webcam
        cap = cv2.VideoCapture(0)
        vehicle_id = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            qr_codes = decode(frame)
            for qr_code in qr_codes:
                vehicle_id = qr_code.data.decode('utf-8')
                cap.release()
                cv2.destroyAllWindows()
                break

            if vehicle_id:
                break

            # Display the frame
            cv2.imshow('QR Code Scanner', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        if not vehicle_id:
            return jsonify({"success": False, "message": "No QR code detected"})

        user_email = session.get('email_id')
        if not user_email:
            return jsonify({"success": False, "message": "User not logged in"})

        # Check if the vehicle exists and is available
        print(vehicle_id)
        vehicle_id=int(vehicle_id)
        cursor.execute("SELECT * FROM vehicle WHERE `v-id` = %s AND `status` = 'Available'", (vehicle_id,))
        vehicle = cursor.fetchall()
        print(vehicle)
        if not vehicle:
            return jsonify({"success": False, "message": "Vehicle not available or does not exist"})

        # Start the ride (update vehicle status and create a new ride entry)
        #cursor.execute("UPDATE vehicle SET `status` = 'in-use' WHERE `v-id` = %s", (vehicle_id,))
        cursor.execute("""
            INSERT INTO ride (`user-id`, `v-id`, `time`, `status`)
            VALUES ((SELECT `user-id` FROM user WHERE email = %s), %s, NOW(), 'ongoing')
        """, (user_email, vehicle_id))
        db.commit()
        # return redirect(url_for('location'))
        #return render_template('location.html')
        return jsonify({"success": True, "vehicle_id": vehicle_id})

    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"success": False, "message": "Failed to start ride"})

@app.route('/check_balance', methods=['POST'])
def check_balance():
    data = request.json
    user_id = data['user_id']
    vehicle_id = data['vehicle_id']

    # Get the vehicle's battery percentage
    cursor.execute("SELECT battery FROM vehicle WHERE `v-id` = %s", (vehicle_id,))
    vehicle = cursor.fetchone()
    if not vehicle:
        return jsonify({"success": False, "message": "Vehicle not found"})

    battery_percentage = vehicle['battery']
    required_balance = battery_percentage * 2

    # Check the user's wallet balance
    cursor.execute("SELECT balance FROM wallet WHERE `user-id` = %s", (user_id,))
    wallet = cursor.fetchone()
    if not wallet:
        return jsonify({"success": False, "message": "Wallet not found"})

    if wallet['balance'] < required_balance:
        return jsonify({"success": False, "message": f"Insufficient balance. You need at least ₹{required_balance} to start the ride."})

    return jsonify({"success": True})

@app.route('/start_ride', methods=['POST', 'GET'])
def start_ride():
    data = request.json
    vehicle_id = data['vehicle_id']
    cursor.execute("UPDATE vehicle SET `status` = 'in-use' WHERE `v-id` = %s", (vehicle_id,))
    

@app.route('/end_ride', methods=['POST'])
def end_ride():
    """Calculate cost and store in DB"""
    data = request.json
    user_id = data['user_id']
    wallet_id = data['wallet_id']
    vehicle_id = data['vehicle_id']
    method = data['method']

    if user_id not in user_tracking:
        return jsonify({"error": "No tracking data found"}), 400

    tracking = user_tracking[user_id]
    total_distance = tracking['distance']
    total_cost = tracking['total_cost']

    cursor.execute("""
        INSERT INTO transaction (`user-id`, `w-id`, `method`, `amount`)
        VALUES (%s, %s, %s, %s)
    """, (user_id, wallet_id, method, total_cost))

    # Deduct the total cost from the user's wallet
    cursor.execute("""
        UPDATE wallet
        SET balance = balance - %s
        WHERE `w-id` = %s
    """, (total_cost, wallet_id))

    # Update vehicle status to "Available"
    cursor.execute("UPDATE vehicle SET `status` = 'Available' WHERE `v-id` = %s", (vehicle_id,))

    db.commit()

    # Clear user tracking data
    del user_tracking[user_id]

    return jsonify({"message": "Ride ended", "total_cost": total_cost})

@app.route('/wallet')
def wallet():
    email = session.get('email_id')

    # Fetch User Details
    cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        return "User not found", 404

    # Fetch Wallet Details
    cursor.execute("SELECT * FROM wallet WHERE `user-id` = %s", (user['user-id'],))
    wallet = cursor.fetchone()

    if not wallet:
        return "Wallet not found", 404

    return render_template('wallet.html', user=user, wallet=wallet)


if __name__ == '__main__':
    app.run(debug=True)