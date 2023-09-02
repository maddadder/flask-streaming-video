from flask import Flask, render_template, request, Response, redirect, url_for, session
from flask_oauthlib.client import OAuth
from azure.identity import DefaultAzureCredential

import cv2
import os
from dotenv import load_dotenv
from functools import wraps
import logging
import json

load_dotenv('.env')

# Configure the logging settings
logging.basicConfig(
    level=logging.INFO,  # Set the desired logging level (e.g., INFO)
    format='%(asctime)s [%(levelname)s] - %(message)s',
    handlers=[
        logging.StreamHandler()  # Output logs to the console
        # Add more handlers here (e.g., logging.FileHandler('logfile.log')) to log to a file
    ]
)

# Azure AD configuration
AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET')
AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
BASE_URI = os.environ.get('BASE_URI')
AUTH_USERS = os.environ.get('AUTH_USERS')
CAMERAS = json.loads(os.environ.get('CAMERAS'))

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.frame_count = 0
app.frame_skip_interval =10

# OAuth configuration
oauth = OAuth(app)
azure = oauth.remote_app(
    'azure',
    consumer_key=AZURE_CLIENT_ID,
    consumer_secret=AZURE_CLIENT_SECRET,
    request_token_params={'scope': 'https://graph.microsoft.com/.default', 'resource': 'https://graph.microsoft.com/'},
    base_url='https://graph.microsoft.com/v1.0/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://login.microsoftonline.com/{}/oauth2/token'.format(AZURE_TENANT_ID),
    authorize_url='https://login.microsoftonline.com/{}/oauth2/authorize'.format(AZURE_TENANT_ID),
)

def gen_frames(camera_url):  # generate frame by frame from camera
    camera = cv2.VideoCapture(camera_url)  # use 0 for web camera
    while True:
        # Capture frame-by-frame
        success, frame = camera.read()  # read the camera frame
        if not success:
            break
        else:
            app.frame_count += 1
            #Process every frame_skip_interval frame
            if app.frame_count % app.frame_skip_interval != 0:
                camera.grab()
                continue

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  # concat frame one by one and show result

# Define a custom authorization decorator
def require_user(allowed_users):
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(*args, **kwargs):
            if 'azure_token' in session:
                if session['userPrincipalName'] in allowed_users:
                    return view_function(*args, **kwargs)
            # If not authorized, redirect to the login page or perform other actions
            return redirect(url_for('login'))
        return wrapper
    return decorator

@app.route('/video_feed')
@require_user(AUTH_USERS)
def video_feed():
    selected_camera = session.get('selected_camera', CAMERAS[0])

    camera_url = 'rtsp://{}:{}@{}:554/cam/realmonitor?channel={}&subtype=0'.format(selected_camera['username'], selected_camera['password'], selected_camera['ip'], selected_camera['channel'])

    return Response(gen_frames(camera_url), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/', methods=['GET', 'POST'])
def index():
    selected_camera_name = session.get('selected_camera', CAMERAS[0]['name'])  # Default to the first camera name

    if request.method == 'POST':
        selected_camera_name = request.form.get('selected_camera_name')
        # Look up the URL based on the selected camera name
        selected_camera = next((camera for camera in CAMERAS if camera['name'] == selected_camera_name), None)
        if selected_camera:
            session['selected_camera'] = selected_camera
    available_cameras = [camera['name'] for camera in CAMERAS]
    return render_template('index.html', available_cameras=available_cameras, selected_camera_name=selected_camera_name)

@app.route('/login')
def login():
    return azure.authorize(callback=REDIRECT_URI)

@app.route('/logout')
def logout():
    # Optional: Revoke the access token (requires additional setup)
    # ...

    # Clear the user's session
    session.pop('azure_token', None)
    session.pop('userPrincipalName', None)
    
    # Redirect to Azure AD logout
    logout_url = 'https://login.microsoftonline.com/{tenant_id}/oauth2/logout?post_logout_redirect_uri={redirect_uri}'
    return redirect(logout_url.format(tenant_id=AZURE_TENANT_ID, redirect_uri=BASE_URI))


@app.route('/login/authorized')
def authorized():
    resp = azure.authorized_response()
    if resp is None or resp.get('access_token') is None:
        return 'Access denied: reason={} error={}'.format(
            request.args['error_reason'],
            request.args['error_description']
        )
    session['azure_token'] = (resp['access_token'], '')
    user_info = azure.get('me')
    session['userPrincipalName'] = user_info.data['userPrincipalName']
    # Redirect to the home page after setting the session
    return redirect(url_for('index'))

@azure.tokengetter
def get_azure_oauth_token():
    return session.get('azure_token')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000,debug=False)