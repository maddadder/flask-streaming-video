from flask import Flask, render_template, Response, redirect, url_for, session
from flask_oauthlib.client import OAuth
from azure.identity import DefaultAzureCredential
import cv2
import os
from dotenv import load_dotenv

load_dotenv('.env')

# Azure AD configuration
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
TENANT_ID = os.environ.get('TENANT_ID')
REDIRECT_URI = os.environ.get('REDIRECT_URI')

camera_url = os.environ.get('CAMERA_URL')

app = Flask(__name__)
app.secret_key = os.urandom(24)

# OAuth configuration
oauth = OAuth(app)
azure = oauth.remote_app(
    'azure',
    consumer_key=CLIENT_ID,
    consumer_secret=CLIENT_SECRET,
    request_token_params={'scope': 'openid email profile'},
    base_url='https://graph.microsoft.com/v1.0/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://login.microsoftonline.com/{}/oauth2/token'.format(TENANT_ID),
    authorize_url='https://login.microsoftonline.com/{}/oauth2/authorize'.format(TENANT_ID),
)

def gen_frames():  # generate frame by frame from camera
    camera = cv2.VideoCapture(camera_url)  # use 0 for web camera
    while True:
        # Capture frame-by-frame
        success, frame = camera.read()  # read the camera frame
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  # concat frame one by one and show result


@app.route('/video_feed')
def video_feed():
    if 'azure_token' in session:
        #Video streaming route. Put this in the src attribute of an img tag
        return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')

@app.route('/login')
def login():
    return azure.authorize(callback=REDIRECT_URI)

@app.route('/logout')
def logout():
    session.pop('azure_token', None)
    return 'Logged out. <a href="/">Home</a>'

@app.route('/login/authorized')
def authorized():
    resp = azure.authorized_response()
    if resp is None or resp.get('access_token') is None:
        return 'Access denied: reason={} error={}'.format(
            request.args['error_reason'],
            request.args['error_description']
        )
    session['azure_token'] = (resp['access_token'], '')
    # user_info = azure.get('me')
    # Redirect to the home page after setting the session
    return redirect(url_for('index'))

@azure.tokengetter
def get_azure_oauth_token():
    return session.get('azure_token')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000,debug=False)