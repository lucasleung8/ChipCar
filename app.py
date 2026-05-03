import flask
from flask import Flask, render_template, request, jsonify, Response, flash
from gpiozero import Servo
from gpiozero import Motor
from gpiozero.pins.lgpio import LGPIOFactory
import cv2
import os
import subprocess
import threading
from dotenv import load_dotenv
import simple_websocket
from flask_socketio import SocketIO, disconnect, emit
import flask_login
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="https://chipcar.cc", async_mode='threading')

# Initialize motors, video, sounds, login
factory = LGPIOFactory()
servo = Servo(12, pin_factory=factory)
motor = Motor(forward=2, backward=3)
motor2 = Motor(forward=4, backward=14)
motor3 = Motor(forward=23, backward=24)
motor4 = Motor(forward=15, backward=18)
speed = 0.8
hornSound = '/home/user/Desktop/ChipCar/Explosion1.ogg'
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

# handle the login functionality
app.config['SECRET_KEY'] = os.urandom(24)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"
# use .env to import the passwords ensuring they aren't public/visible
users = { 'lucas': {'password': os.getenv('LUCAS_PASSWORD')},
         'soyul': {'password': os.getenv('SOYUL_PASSWORD')},
         'jay': {'password': os.getenv('JAY_PASSWORD')},
         'anthony': {'password': os.getenv('ANTHONY_PASSWORD')}
        }
admin = {'admin': {'password': os.getenv('ADMIN_PASSWORD')}}

# mutex (mutual exclusion) slot - keep track of which user is currently driving, allowing only one session at a time
active_user = {
    'username': None
}

class User(UserMixin):
    pass

@login_manager.user_loader
def user_loader(username):
    if username not in users and username not in admin:
        return

    user = User()
    user.id = username
    return user

@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    if username not in users and username not in admin:
        return

    user = User()
    user.id = username
    return user

# login page, checks login details and if there is already another user, when trying to log in
@app.route('/login', methods=['GET', 'POST'])
def login():
    # POST requests come from form submission, not visting the url
    if flask.request.method == 'POST':
        username = request.form['username']

        # user logs in
        if username in users and request.form['password'] == users[username]['password']:
            if active_user['username'] is None:
                user = User()
                user.id = username
                login_user(user)
                active_user['username'] = username
                return flask.redirect('/')
            else:
                flash('Car currently being used by ' + active_user['username'] + '. Please tell them to logout or ask the admin to kick them out :)', 'error')
        # admin logs in
        elif username in admin and request.form['password'] == admin[username]['password']:
                user = User()
                user.id = username
                login_user(user)
                return flask.redirect('/admin')
        else:
            flash('Invalid login, please try again.', 'error')
            print()
            
    # if someone already logged in tries to visit the login page again, redirect them
    if current_user.is_authenticated:
        if current_user.id in admin:
            return flask.redirect('/admin') 
        return flask.redirect('/')

    # show the login page
    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    # user (driver) trying to log out -> clear the active user slot
    if active_user['username'] == current_user.id:
        active_user['username'] = None
        motor.stop()
        motor2.stop()
        motor3.stop()
        motor4.stop()
        servo.value = 0
    # otherwise, the admin is trying to log out, and so we don't clear the active user slot.
    logout_user()
    return flask.redirect('/')


# generate the live video
def generate_frames():
    while True:
        _, frame = cap.read()
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
               buffer.tobytes() + b'\r\n')

@app.route('/video')
@login_required
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# returns the main (index) page
@app.route('/')
@login_required
def index():
    if current_user.id in admin:
        return flask.redirect('/admin') 
    return render_template('index.html')

# check that the user is actually an admin
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def adminPage():
    if flask.request.method == 'POST':
        # subprocess.Popen(["pkill", "-9", "-f", "gunicorn"])
        socketio.emit('logout_signal', {'reason': f"An admin has kicked you out."})
        active_user['username'] = None
        motor.stop()
        motor2.stop()
        motor3.stop()
        motor4.stop()
        servo.value = 0
        return flask.redirect('/admin')

    # visiting the admin page normally
    if current_user.id in admin:
       return render_template('admin.html', active_user=active_user)
    else:
       return flask.redirect('/')

# play sounds when website sends a sound signal
@app.route('/sound', methods=['POST'])
@login_required
def sound():
    # reject unauthorized move commands
    if active_user['username'] != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        # return flask.Response("Unauthorized", status=403)

    signal = request.get_json().get('type')
    if signal == 'horn':
        subprocess.Popen(['ffplay', '-nodisp', '-autoexit', hornSound])
    return jsonify({"status": "success"})

# control servos when website sends button signals
@app.route('/move', methods=['POST'])
@login_required
def move():
    # reject unauthorized move commands
    if active_user['username'] != current_user.id:
        return flask.Response("Unauthorized", status=403)

    direction = request.get_json().get('direction')
    if direction == 'forward':
        motor.forward(speed)
        motor2.forward(speed)
        motor3.forward(speed)
        motor4.forward(speed)
    elif direction == 'back':
        motor.backward(speed)
        motor2.backward(speed)
        motor3.backward(speed)
        motor4.backward(speed)
    elif direction == 'left':
        servo.value = 1
    elif direction == 'right':
        servo.value = -1
    elif direction == 'stop':
        motor.stop()
        motor2.stop()
        motor3.stop()
        motor4.stop()
        servo.value = 0
    return render_template('index.html')

# web sockets be wildin -> once user has logged in and gotten to the index page
@socketio.on('connect')
def handle_connect():
    if not current_user.is_authenticated:
        disconnect()
        return
    # allow the user to continue if slot is empty or the user connecting is already the active user
    if active_user['username'] is None or active_user['username'] == current_user.id:
        active_user['username'] = current_user.id
        emit('allowed')
        # print(f"{current_user.id} took control")
    else:
        emit('logout_signal', {'reason': f"Car is in use by {active_user['username']}. Please tell them to logout :)"})
        disconnect()

# user has discon
@socketio.on('disconnect')
def handle_disconnect():
    # check if user is logged in before trying to access .id -> someone who connects but doesn't login and just closes the tab
    # wont cause any errors
    if current_user.is_authenticated:
        if active_user['username'] == current_user.id:
            active_user['username'] = None
            motor.stop()
            motor2.stop()
            motor3.stop()
            motor4.stop()
            servo.value = 0


if __name__ == '__main__':
    # pls run run.sh instead if you can, its faster
    app.run(port=8000)
