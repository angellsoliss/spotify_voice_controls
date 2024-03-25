from dotenv import load_dotenv
import os
from flask import Flask, redirect, jsonify, session, request, url_for, render_template
import requests
import urllib
from datetime import datetime
import spotipy
import speech_recognition as sr
import threading
import pyttsx3

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
    #initialize text to speech
    engine = pyttsx3.init()
    global listening
    #create spotipy object, pass access token
    sp = spotipy.Spotify(auth=access_token)
    while listening:
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.7)
                audio = r.listen(source, phrase_time_limit=3)
                speech = r.recognize_google(audio)
                speech = speech.lower()
                
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
                elif speech == "mute":
                    sp.volume(0, device_id=None)
                    print(speech)
                elif speech == "volume 25":
                    sp.volume(25, device_id=None)
                    print(speech)
                elif speech == "volume 50":
                    sp.volume(50, device_id=None)
                    print(speech)
                elif speech == "volume 75":
                    sp.volume(75, device_id=None)
                    print(speech)
                elif speech == "max volume":
                    sp.volume(100, device_id=None)
                    print(speech)
                elif speech == "exit":
                    listening = False
                    break
                elif speech == "shuffle":
                    engine.say("shuffle enabled")
                    engine.runAndWait()
                    sp.shuffle(state=True, device_id=None)
                    print(speech)
                elif speech == "shuffle off":
                    engine.say("shuffle disabled")
                    engine.runAndWait()
                    sp.shuffle(state=False, device_id=None)
                    print(speech)
                elif speech == "save":
                    uri_exists = False
                    current_song_uri = get_current_song(access_token)
                    extracted_current_song_uri = current_song_uri[0]
 
                    for track_uri in selected_playlist_track_uris:
                        if track_uri == extracted_current_song_uri:
                            print("current song: " + extracted_current_song_uri)
                            print("already exists: " + track_uri)
                            uri_exists = True

                    if not playlist_id:
                        engine.say("no playlist selected")
                        engine.runAndWait()
                        print("no playlist selected...")

                    elif uri_exists:
                        engine.say("song already in playlist")
                        engine.runAndWait()
                        print("song already in playlist")

                    else:
                        if current_song_uri:
                            try:
                                sp.user_playlist_add_tracks(user_id, playlist_id, current_song_uri, None)
                                engine.say("track added to playlist")
                                engine.runAndWait()
                                print("Track added to the playlist.")
                            except Exception as e:
                                print("Error adding track to the playlist:", e)
                        else:
                            print("No track currently playing.")
                else:
                    print(speech + " unknown command...")
        
        except sr.RequestError as e:
            print("could not request results; {0}".format(e))
        
        except sr.UnknownValueError:
            print(speech + " error occurred")
        
        except Exception as ex:
            print("unexpected error:", ex)

def get_all_playlist_tracks(sp, playlist_id):
    offset = 0
    all_tracks = []

    while True:
        tracks = sp.playlist_items(playlist_id, offset=offset)
        all_tracks.extend(tracks['items'])

        if len(tracks['items']) == 0:
            break

        offset += len(tracks['items'])

    return all_tracks

def get_current_song(access_token):
    sp = spotipy.Spotify(auth=access_token)
    if listening:
        track = sp.current_user_playing_track()
        if track and 'item' in track and 'uri' in track['item']:
            return [track['item']['uri']]
        else:
            return []  # Return empty list if track URI is not available
    else:
        return []


#home page, prompt user to log in with their spotify account
@app.route('/')
def index():
    return render_template('index.html')

#login page
@app.route('/login', methods=['POST'])
def login():
    scope = 'user-modify-playback-state user-read-playback-state playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative'

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

@app.route('/media_control', methods=['POST', 'GET'])
def media_control():
    #check if access token is present within session
    if 'access_token' not in session:
        #if access token is not present, prompt user to login again
        return redirect('/login')
    
    #otherwise, check if access token has expired
    if datetime.now().timestamp() > session['expires_at']:
        #if token has expired, refresh token
        return redirect('/refresh-token')

    sp = spotipy.Spotify(auth=session['access_token'])

    #get user id
    global user_id
    user_id = sp.current_user()['id']

    #get user playlists
    playlists = sp.current_user_playlists()['items']

    global playlist_info
    #display playlist names on html page
    playlist_info = []
    for playlist in playlists:
        playlist_info.append((playlist['name'], playlist['id']))
    
    global playlist_name
    playlist_name = None

    #if playlist is selected
    if request.method == 'POST':
        global playlist_id
        global selected_playlist_track_uris
        selected_playlist_track_uris = []
        playlist_id = request.form.get('playlist_id', '')
        for name, i in playlist_info:
            if i == playlist_id:
                playlist_name = name
                break
        
        selected_playlist_tracks = get_all_playlist_tracks(sp, playlist_id)
        for track in selected_playlist_tracks:
            track_uri = track['track']['uri']
            selected_playlist_track_uris.append(track_uri)

        print(playlist_name)
        print(playlist_id)
    
    return render_template('mediaControl.html', playlist_info=playlist_info, playlist_name=playlist_name)


@app.route('/listen')
def listen():
    global listening
    listening = True
    access_token = session['access_token']
    threading.Thread(target=listen_for_commands, args=(access_token,)).start()
    return render_template('mediaControl.html', playlist_info=playlist_info, playlist_name=playlist_name)

@app.route('/stopListening')
def stopListening():
    global listening
    listening = False
    return render_template('mediaControl.html', playlist_info=playlist_info, playlist_name=playlist_name)


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
