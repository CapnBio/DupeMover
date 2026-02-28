import os
import json
import logging
import uuid
import requests
import time
import shutil
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, Unauthorized

app = Flask(__name__)

# --- Persistent Config & Session Management ---
CONFIG_FILE = 'config.json'

def load_config():
    defaults = {
        "app_password": "admin",
        "secret_key": os.urandom(24).hex(),
        "plex_token": None,
        "plex_baseurl": None,
        "server_name": None,
        "target_folders": []
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            try:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key, val in defaults.items():
                    if key not in config:
                        config[key] = val
                return config
            except:
                pass
    return defaults

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Global Config Object
config = load_config()
save_config(config)

app.secret_key = bytes.fromhex(config["secret_key"])
app.permanent_session_lifetime = timedelta(days=30)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constants for Plex Auth ---
PLEX_HEADERS = {
    'X-Plex-Product': 'DupeMover',
    'X-Plex-Client-Identifier': 'dupemover-' + str(uuid.getnode()),
    'X-Plex-Device': 'Web Browser',
    'X-Plex-Platform': 'Linux',
    'X-Plex-Device-Name': 'DupeMover',
    'Accept': 'application/json'
}

def get_plex_server():
    # Use saved config first
    token = config.get('plex_token')
    baseurl = config.get('plex_baseurl')
    
    if not token or not baseurl:
        return None
    try:
        return PlexServer(baseurl, token)
    except Exception as e:
        logger.error(f"Failed to connect to Plex: {e}")
        return None

def format_size(size_bytes):
    if size_bytes == 0: return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(os.math.floor(os.math.log(size_bytes, 1024)))
    p = os.math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

app.jinja_env.filters['format_size'] = format_size

# --- Routes ---

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if not config.get('plex_token'):
        return redirect(url_for('setup_plex'))

    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == config.get('app_password'):
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Invalid password', 'error')
    return render_template('login.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_password':
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            if new_password != confirm_password:
                flash('Passwords do not match', 'error')
            elif len(new_password) < 4:
                flash('Password must be at least 4 characters long', 'error')
            else:
                config['app_password'] = new_password
                save_config(config)
                flash('Password updated successfully', 'success')
        
        elif action == 'clear_plex':
            config['plex_token'] = None
            config['plex_baseurl'] = None
            config['server_name'] = None
            save_config(config)
            flash('Plex connection cleared.', 'success')
        
        elif action == 'add_folder':
            new_folder = request.form.get('new_folder')
            if new_folder and os.path.exists(new_folder):
                if new_folder not in config['target_folders']:
                    config['target_folders'].append(new_folder)
                    save_config(config)
                    flash('Target folder added successfully', 'success')
                else:
                    flash('Folder already exists in target folders', 'info')
            else:
                flash('Folder path does not exist on disk', 'error')
        
        elif action == 'remove_folder':
            folder_to_remove = request.form.get('folder_path')
            if folder_to_remove in config['target_folders']:
                config['target_folders'].remove(folder_to_remove)
                save_config(config)
                flash('Target folder removed', 'success')

        elif action == 'full_reset':
            # Reset to defaults
            config['app_password'] = "admin"
            config['plex_token'] = None
            config['plex_baseurl'] = None
            config['server_name'] = None
            config['target_folders'] = []
            save_config(config)
            session.clear()
            flash('Application has been fully reset to defaults.', 'success')
            return redirect(url_for('login'))
            
    return render_template('settings.html', 
                           plex_server=config.get('server_name'), 
                           target_folders=config.get('target_folders', []))

@app.route('/setup')
def setup_plex():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('setup.html')

# --- Plex Auth API ---

@app.route('/auth/plex/start')
def plex_auth_start():
    try:
        resp = requests.post('https://plex.tv/api/v2/pins?strong=true', headers=PLEX_HEADERS, timeout=10)
        if resp.status_code != 201:
             return jsonify({'error': f'Plex API returned {resp.status_code}'}), 500
        data = resp.json()
        pin_id = data.get('id')
        code = data.get('code')
        client_id = PLEX_HEADERS['X-Plex-Client-Identifier']
        auth_url = f"https://app.plex.tv/auth/#!?clientID={client_id}&code={code}&context%5Bdevice%5D%5Bproduct%5D=DupeMover"
        return jsonify({'pin_id': pin_id, 'auth_url': auth_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/auth/plex/check/<pin_id>')
def plex_auth_check(pin_id):
    try:
        resp = requests.get(f'https://plex.tv/api/v2/pins/{pin_id}', headers=PLEX_HEADERS, timeout=10).json()
        token = resp.get('authToken')
        if token:
            account = MyPlexAccount(token=token)
            resources = [r for r in account.resources() if r.product == 'Plex Media Server']
            servers = []
            for r in resources:
                uri = r.connections[0].uri if r.connections else None
                servers.append({'name': r.name, 'uri': uri, 'token': r.accessToken})
            return jsonify({'status': 'authorized', 'token': token, 'servers': servers})
        else:
            return jsonify({'status': 'waiting'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/auth/plex/save', methods=['POST'])
def plex_auth_save():
    data = request.json
    config['plex_token'] = data.get('token')
    config['plex_baseurl'] = data.get('uri')
    config['server_name'] = data.get('name')
    save_config(config)
    return jsonify({'success': True})

# --- Main Dashboard Routes ---

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if not config.get('server_name'):
        return redirect(url_for('setup_plex'))
    return render_template('dashboard.html', server_name=config.get('server_name'))

@app.route('/scan')
def scan_duplicates():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    server = get_plex_server()
    if not server:
        return jsonify({'error': 'Plex not connected'}), 400
    
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 20))
    duplicates = []
    found_count = 0
    try:
        current_idx = 0
        for section in server.library.sections():
            if section.type in ['movie', 'show']:
                items = section.search(duplicate=True)
                for item in items:
                    if current_idx >= offset:
                        # Reload to get full metadata (streams, languages, etc.)
                        try:
                            item.reload()
                        except:
                            pass
                            
                        if section.type == 'movie':
                            if len(item.media) > 1:
                                duplicates.append({'type': 'Movie', 'title': item.title, 'key': item.key, 'files': serialize_media(item.media)})
                                found_count += 1
                        elif section.type == 'show':
                            for episode in item.episodes():
                                if len(episode.media) > 1:
                                    # Reload episode for metadata
                                    try:
                                        episode.reload()
                                    except:
                                        pass
                                    duplicates.append({'type': 'Episode', 'title': f"{item.title} - S{episode.seasonNumber}E{episode.index} - {episode.title}", 'key': episode.key, 'files': serialize_media(episode.media)})
                                    found_count += 1
                        if found_count >= limit: break
                    current_idx += 1
                if found_count >= limit: break
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'items': duplicates, 'has_more': found_count >= limit})

def serialize_media(media_list):
    data = []
    for media in media_list:
        for part in media.parts:
            # Extract audio languages
            languages = []
            for stream in part.streams:
                if stream.streamType == 2: # Audio stream
                    lang = stream.language if stream.language else stream.languageCode
                    if not lang: lang = "Unknown"
                    if lang not in languages:
                        languages.append(lang)
            
            data.append({
                'id': part.id,
                'file': part.file,
                'size': part.size,
                'resolution': media.videoResolution,
                'codec': media.videoCodec,
                'languages': languages
            })
    return data

@app.route('/folders')
def get_folders():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'folders': config.get('target_folders', [])})

@app.route('/plex_folders')
def get_plex_folders():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    server = get_plex_server()
    if not server:
        return jsonify({'error': 'Plex not connected'}), 400
    
    folders = set()
    try:
        for section in server.library.sections():
            for location in section.locations:
                folders.add(location)
        return jsonify({'folders': sorted(list(folders))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/move', methods=['POST'])
def move_file():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    file_path = data.get('file_path')
    target_dir = data.get('target_dir')
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'Source file not found'}), 404
    if not target_dir or not os.path.exists(target_dir):
        return jsonify({'error': 'Target directory not found'}), 404
        
    try:
        dest_path = os.path.join(target_dir, os.path.basename(file_path))
        if os.path.exists(dest_path):
             return jsonify({'error': 'File already exists at destination'}), 400
             
        shutil.move(file_path, dest_path)
        return jsonify({'success': True, 'new_path': dest_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/move_bulk', methods=['POST'])
def move_bulk():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    file_paths = data.get('file_paths', [])
    target_dir = data.get('target_dir')
    
    if not target_dir or not os.path.exists(target_dir):
        return jsonify({'error': 'Target directory not found'}), 400
    
    results = []
    for file_path in file_paths:
        if not file_path or not os.path.exists(file_path):
            results.append({'file': file_path, 'success': False, 'error': 'File not found'})
            continue
        try:
            dest_path = os.path.join(target_dir, os.path.basename(file_path))
            if os.path.exists(dest_path):
                 results.append({'file': file_path, 'success': False, 'error': 'File already exists at destination'})
                 continue
            shutil.move(file_path, dest_path)
            results.append({'file': file_path, 'success': True})
        except Exception as e:
            results.append({'file': file_path, 'success': False, 'error': str(e)})
            
    return jsonify({'results': results})

@app.route('/delete', methods=['POST'])
def delete_file():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    file_path = data.get('file_path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    try:
        os.remove(file_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_bulk', methods=['POST'])
def delete_bulk():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    file_paths = data.get('file_paths', [])
    
    results = []
    for file_path in file_paths:
        if not file_path or not os.path.exists(file_path):
            results.append({'file': file_path, 'success': False, 'error': 'File not found'})
            continue
        try:
            os.remove(file_path)
            results.append({'file': file_path, 'success': True})
        except Exception as e:
            results.append({'file': file_path, 'success': False, 'error': str(e)})
            
    return jsonify({'results': results})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5055, debug=True)
