from dotenv import load_dotenv
import os
from flask import Flask, redirect, jsonify, session, request, url_for, render_template
import requests
import urllib
from datetime import datetime
import spotipy
import speech_recognition as sr
import threading

load_dotenv()
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

REDIRECT_URI = "http://localhost:5000/callback"

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY")
#url to authorize user
AUTH_URL = "https://accounts.spotify.com/authorize"

#url to refresh token
TOKEN_URL = "https://accounts.spotify.com/api/token"

global listening
listening = False

r = sr.Recognizer()

def listen_for_commands(access_token):
    global listening
    #create spotipy object, pass access token
    sp = spotipy.Spotify(auth=access_token)
    while listening:
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.7)
                audio = r.listen(source)
                speech = r.recognize_google(audio)
                
                if speech == "next":
                    sp.next_track(device_id=None)
                    print(speech)
                elif speech == "previous":
                    sp.previous_track(device_id=None)
                    print(speech)
                elif speech == "pause":
                    sp.pause_playback(device_id=None)
                    print(speech)
                elif speech == "play":
                    sp.start_playback(device_id=None)
                    print(speech)
                elif speech == "exit":
                    break
                else:
                    print(speech + "unknown command...")
        
        except sr.RequestError as e:
            print("could not request results; {0}".format(e))
        
        except sr.UnknownValueError:
            print(speech + "error occurred")


#home page, prompt user to log in with their spotify account
@app.route('/')
def index():
    return render_template('index.html')

#login page
@app.route('/login', methods=['POST'])
def login():
    scope = 'user-modify-playback-state user-read-playback-state'

    params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI,
        'show_dialog': True
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    #redirect user to authorization page
    return redirect(auth_url)

@app.route('/callback')
def callback():
    #check if error occured while logging in
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    #if user successfully logs in
    if 'code' in request.args:
        #create request_body to exchange it for access token
        request_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
            'client_id': client_id,
            'client_secret': client_secret
        }

        #send request body to token url to get access token
        response = requests.post(TOKEN_URL, data=request_body)
        #store token info
        token_info = response.json()

        #store acces token and refresh token within session
        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']

        #store token expiration date within token
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']

        #redirect user to app functionality page
        return redirect('/media_control')

@app.route('/media_control')
def media_control():
    #check if access token is present within session
    if 'access_token' not in session:
        #if access token is not present, prompt user to login again
        return redirect('/login')
    
    #otherwise, check if access token has expired
    if datetime.now().timestamp() > session['expires_at']:
        #if token has expired, refresh token
        return redirect('/refresh-token')
    
    return render_template('mediaControl.html')

@app.route('/listen')
def listen():
    global listening
    listening = True
    access_token = session['access_token']
    threading.Thread(target=listen_for_commands, args=(access_token,)).start()
    return redirect('media_control')

@app.route('/stopListening')
def stopListening():
    global listening
    listening = False
    return redirect('media_control')


@app.route('/refresh-token')
def refresh():
    #check if refresh token is in session
    if 'refresh_token' not in session:
        #if refresh token is not in session, prompt user to log in again
        redirect('/login')
    
    #otherwise, check if access token has expired
    if datetime.now().timestamp() > session['expires_at']:
        #build request body
        request_body = {
            'grant-type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': client_id,
            'client_secret': client_secret
        }

        #request fresh access token using request body
        response = requests.post(TOKEN_URL, data=request_body)
        #store fresh token
        new_token_info = response.json()

        #update session token/expires_at values
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']

        #redirect user
        return redirect('/media_control')

#run app
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, threaded=True)