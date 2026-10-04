#!/usr/bin/env python3
"""
🔍 Facebook Activity Tracker v3.0 - Production Ready
Real-time status tracking, last seen scraper, stable session management
"""

import os
import json
import logging
import threading
import time
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, request
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FB_EMAIL = os.getenv("FB_EMAIL")
FB_PASSWORD = os.getenv("FB_PASSWORD")
PORT = int(os.getenv("PORT", 10000))

if not all([TELEGRAM_BOT_TOKEN, FB_EMAIL, FB_PASSWORD]):
    logger.warning("⚠️ Missing env vars - limited functionality")

DB_FILE = "facebook_tracker.db"
COOKIES_FILE = "fb_cookies.json"
app = Flask(__name__)

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

class TrackerDB:
    @staticmethod
    def init():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY,
            fb_id TEXT UNIQUE,
            name TEXT,
            profile_url TEXT,
            user_id INTEGER,
            created_at TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY,
            fb_id TEXT,
            status TEXT,
            last_seen TEXT,
            online_status TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY(fb_id) REFERENCES targets(fb_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER UNIQUE,
            cookies TEXT,
            last_login TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    
    @staticmethod
    def add_target(fb_id, name, profile_url, user_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute('INSERT INTO targets (fb_id, name, profile_url, user_id, created_at) VALUES (?, ?, ?, ?, ?)',
                      (fb_id, name, profile_url, user_id, datetime.now()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    @staticmethod
    def log_activity(fb_id, status, last_seen, online_status="unknown"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO activity (fb_id, status, last_seen, online_status, timestamp) VALUES (?, ?, ?, ?, ?)',
                  (fb_id, status, last_seen, online_status, datetime.now()))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_activity(fb_id, limit=15):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT status, last_seen, online_status, timestamp FROM activity WHERE fb_id=? ORDER BY timestamp DESC LIMIT ?',
                  (fb_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows
    
    @staticmethod
    def get_latest_activity(fb_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT status, last_seen, online_status, timestamp FROM activity WHERE fb_id=? ORDER BY timestamp DESC LIMIT 1',
                  (fb_id,))
        row = c.fetchone()
        conn.close()
        return row
    
    @staticmethod
    def get_targets(user_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT fb_id, name, profile_url FROM targets WHERE user_id=?', (user_id,))
        rows = c.fetchall()
        conn.close()
        return rows
    
    @staticmethod
    def remove_target(fb_id, user_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM targets WHERE fb_id=? AND user_id=?', (fb_id, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def save_cookies(cookies):
        try:
            with open(COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
        except:
            pass
    
    @staticmethod
    def load_cookies():
        try:
            if Path(COOKIES_FILE).exists():
                with open(COOKIES_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return None

TrackerDB.init()

# ============================================================================
# FACEBOOK SESSION MANAGER (LIGHTWEIGHT)
# ============================================================================

class FacebookSessionManager:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.is_logged_in = False
        self.setup_session()
        self.load_or_create_session()
    
    def setup_session(self):
        """Setup session with retries and proper headers"""
        retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],    ← এটা সঠিক
    backoff_factor=1
)
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def load_or_create_session(self):
        """Load saved cookies or create new session"""
        cookies = TrackerDB.load_cookies()
        if cookies:
            self.session.cookies.update(cookies)
            if self.verify_session():
                self.is_logged_in = True
                logger.info("✅ Loaded existing Facebook session")
                return
        
        logger.info("🔑 Creating new Facebook session...")
        self.login()
    
    def login(self):
        """Login to Facebook using credentials"""
        try:
            # Get login page
            resp = self.session.get('https://www.facebook.com/login.php', timeout=10)
            
            # Extract form data
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Prepare login data
            login_data = {
                'email': self.email,
                'pass': self.password,
                'login': 'Log In'
            }
            
            # Send login request
            login_resp = self.session.post(
                'https://www.facebook.com/login.php',
                data=login_data,
                timeout=10,
                allow_redirects=True
            )
            
            # Check if logged in
            if 'c_user' in self.session.cookies:
                self.is_logged_in = True
                TrackerDB.save_cookies(dict(self.session.cookies))
                logger.info("✅ Facebook login successful")
                return True
            else:
                logger.warning("⚠️ Login may have failed - checking profile access")
                # Try to verify
                if self.verify_session():
                    self.is_logged_in = True
                    TrackerDB.save_cookies(dict(self.session.cookies))
                    return True
        
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
        
        return False
    
    def verify_session(self):
        """Verify session is valid"""
        try:
            resp = self.session.get('https://www.facebook.com/', timeout=10)
            return 'logout' in resp.text.lower() or 'profile' in resp.text.lower()
        except:
            return False
    
    def get_profile_info(self, profile_url):
        """Scrape profile status and last seen"""
        try:
            resp = self.session.get(profile_url, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            status = "offline"
            last_seen = "unknown"
            
            # Parse HTML for activity status
            page_text = resp.text
            
            # Check for "Active now"
            if "Active now" in page_text or "active_now" in page_text:
                status = "online"
                last_seen = "now"
            # Check for time patterns
            elif "Active" in page_text and "ago" in page_text:
                # Extract time ago (e.g., "Active 5m ago")
                import re
                match = re.search(r'Active\s+(\d+\s*(?:m|h|d)\s*ago)', page_text)
                if match:
                    last_seen = match.group(1)
                    status = "seen_recently"
            
            # Get name from profile
            name = "Unknown"
            title_elem = soup.find('title')
            if title_elem:
                name = title_elem.text.split('|')[0].strip()
            
            return {
                'name': name,
                'status': status,
                'last_seen': last_seen,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"❌ Scrape error: {e}")
            return None
    
    def extract_fb_id(self, url):
        """Extract FB ID or username from URL"""
        try:
            if 'facebook.com/' not in url:
                return None
            
            # Handle profile.php?id=123456
            if 'profile.php?id=' in url:
                return url.split('id=')[1].split('&')[0]
            
            # Handle /username/
            parts = url.split('facebook.com/')
            if len(parts) > 1:
                username = parts[1].split('/')[0].split('?')[0]
                if username and username not in ['login', 'help', 'unsupported']:
                    return username
        
        except:
            pass
        
        return None

fb_manager = FacebookSessionManager(FB_EMAIL, FB_PASSWORD)

# ============================================================================
# ACTIVITY TRACKER ENGINE
# ============================================================================

class ActivityTracker:
    def __init__(self):
        self.tracking = {}
        self.lock = threading.Lock()
        self.check_interval = 300  # 5 minutes default
    
    def add_target(self, user_id, profile_url):
        """Add profile to tracking"""
        fb_id = fb_manager.extract_fb_id(profile_url)
        
        if not fb_id:
            return False, "❌ Invalid Facebook URL"
        
        # Get initial info
        info = fb_manager.get_profile_info(profile_url)
        if not info:
            return False, "❌ Cannot access profile"
        
        # Save to DB
        if not TrackerDB.add_target(fb_id, info['name'], profile_url, user_id):
            return False, "⚠️ Already tracking this profile"
        
        # Start tracking
        with self.lock:
            self.tracking[fb_id] = {
                'user_id': user_id,
                'url': profile_url,
                'active': True,
                'last_status': info['status'],
                'last_seen': info['last_seen'],
                'last_check': datetime.now(),
                'check_count': 0
            }
        
        # Start background monitor
        threading.Thread(target=self._monitor_loop, args=(fb_id,), daemon=True).start()
        
        logger.info(f"🔍 Tracking started: {info['name']} ({fb_id})")
        return True, f"✅ Tracking *{info['name']}*\nChecks every 5 minutes"
    
    def _monitor_loop(self, fb_id):
        """Background monitoring loop"""
        while True:
            try:
                with self.lock:
                    if fb_id not in self.tracking:
                        break
                    track = self.tracking[fb_id]
                
                # Check if should run
                if not track.get('active'):
                    time.sleep(60)
                    continue
                
                # Get latest info
                info = fb_manager.get_profile_info(track['url'])
                if info:
                    old_status = track['last_status']
                    old_last_seen = track['last_seen']
                    
                    # Log to DB
                    TrackerDB.log_activity(
                        fb_id,
                        info['status'],
                        info['last_seen'],
                        "online" if info['status'] == "online" else "offline"
                    )
                    
                    # Update tracking
                    with self.lock:
                        if fb_id in self.tracking:
                            self.tracking[fb_id]['last_status'] = info['status']
                            self.tracking[fb_id]['last_seen'] = info['last_seen']
                            self.tracking[fb_id]['last_check'] = datetime.now()
                            self.tracking[fb_id]['check_count'] += 1
                    
                    # Log changes
                    if info['status'] != old_status:
                        logger.info(f"⚠️ {fb_id} status: {old_status} → {info['status']}")
                
                time.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"Monitor error ({fb_id}): {e}")
                time.sleep(120)
    
    def stop_tracking(self, fb_id, user_id):
        """Stop tracking"""
        with self.lock:
            if fb_id in self.tracking and self.tracking[fb_id]['user_id'] == user_id:
                self.tracking[fb_id]['active'] = False
                del self.tracking[fb_id]
                TrackerDB.remove_target(fb_id, user_id)
                logger.info(f"🛑 Stopped: {fb_id}")
                return True
        return False
    
    def get_status(self, fb_id):
        """Get current status"""
        with self.lock:
            if fb_id in self.tracking:
                track = self.tracking[fb_id]
                return {
                    'active': True,
                    'name': track.get('name', fb_id),
                    'status': track['last_status'],
                    'last_seen': track['last_seen'],
                    'last_check': track['last_check'].isoformat(),
                    'checks': track['check_count']
                }
        
        # Try DB
        latest = TrackerDB.get_latest_activity(fb_id)
        if latest:
            return {
                'active': False,
                'status': latest[0],
                'last_seen': latest[1],
                'timestamp': latest[3]
            }
        
        return {'active': False, 'status': 'unknown'}
    
    def get_history(self, fb_id, limit=20):
        """Get activity history"""
        rows = TrackerDB.get_activity(fb_id, limit)
        return [{
            'status': r[0],
            'last_seen': r[1],
            'online': r[2],
            'timestamp': r[3]
        } for r in rows]

tracker = ActivityTracker()

# ============================================================================
# FLASK API ENDPOINTS
# ============================================================================

@app.route('/', methods=['GET'])
def health():
    return jsonify({
        'status': 'running',
        'service': 'Facebook Activity Tracker v3.0',
        'timestamp': datetime.now().isoformat(),
        'fb_authenticated': fb_manager.is_logged_in
    }), 200

@app.route('/api/targets/<int:user_id>', methods=['GET'])
def get_targets(user_id):
    targets = TrackerDB.get_targets(user_id)
    return jsonify({
        'count': len(targets),
        'targets': [{'fb_id': t[0], 'name': t[1], 'url': t[2]} for t in targets]
    }), 200

@app.route('/api/status/<fb_id>', methods=['GET'])
def get_status_api(fb_id):
    return jsonify(tracker.get_status(fb_id)), 200

@app.route('/api/history/<fb_id>', methods=['GET'])
def get_history_api(fb_id):
    limit = request.args.get('limit', 20, type=int)
    return jsonify({
        'fb_id': fb_id,
        'history': tracker.get_history(fb_id, limit)
    }), 200

@app.route('/api/stats', methods=['GET'])
def get_stats():
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'active_tracking': len(tracker.tracking)
    }), 200

# ============================================================================
# TELEGRAM BOT INTEGRATION
# ============================================================================

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
    
    def get_updates(self):
        try:
            resp = requests.post(
                f"{self.base_url}/getUpdates",
                json={"offset": self.offset, "timeout": 30},
                timeout=35
            )
            data = resp.json()
            return data.get('result', []) if data.get('ok') else []
        except Exception as e:
            logger.error(f"Get updates error: {e}")
            return []
    
    def send_message(self, chat_id, text, parse_mode="Markdown"):
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                },
                timeout=10
            )
        except Exception as e:
            logger.error(f"Send message error: {e}")
    
    def send_menu(self, chat_id):
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "🔍 *Facebook Activity Tracker v3.0*\n\nReal-time profile monitoring",
                    "parse_mode": "Markdown",
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": "➕ Add Profile", "callback_data": "add_profile"},
                             {"text": "📊 My Profiles", "callback_data": "list_profiles"}],
                            [{"text": "🔴 Online Status", "callback_data": "online_status"},
                             {"text": "📋 History", "callback_data": "history"}]
                        ]
                    }
                },
                timeout=10
            )
        except Exception as e:
            logger.error(f"Send menu error: {e}")
    
    def handle_update(self, update):
        if 'message' in update:
            self.handle_message(update['message'])
        elif 'callback_query' in update:
            self.handle_callback(update['callback_query'])
        
        self.offset = update.get('update_id', 0) + 1
    
    def handle_message(self, message):
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        user_id = message['from']['id']
        
        if text == '/start':
            self.send_menu(chat_id)
        
        elif text == '/help':
            self.send_message(chat_id,
                "*Commands:*\n"
                "`/start` - Menu\n"
                "`/add URL` - Add profile\n"
                "`/list` - My profiles\n"
                "`/status ID` - Check status\n"
                "`/stop ID` - Stop tracking\n"
                "`/history ID` - View history"
            )
        
        elif text == '/list':
            targets = TrackerDB.get_targets(user_id)
            if targets:
                msg = "*Your Profiles:*\n\n"
                for t in targets:
                    msg += f"👤 *{t[1]}*\n`{t[0]}`\n"
            else:
                msg = "❌ No profiles tracked"
            self.send_message(chat_id, msg)
        
        elif text.startswith('/add '):
            url = text[5:].strip()
            success, msg = tracker.add_target(user_id, url)
            self.send_message(chat_id, msg)
        
        elif text.startswith('/status '):
            fb_id = text[8:].strip()
            status = tracker.get_status(fb_id)
            if status.get('active'):
                msg = (f"🔴 *{fb_id}*\n"
                       f"Status: `{status['status']}`\n"
                       f"Last Seen: `{status['last_seen']}`\n"
                       f"Last Check: `{status['last_check']}`")
            else:
                msg = "❌ Not actively tracking"
            self.send_message(chat_id, msg)
        
        elif text.startswith('/stop '):
            fb_id = text[6:].strip()
            if tracker.stop_tracking(fb_id, user_id):
                self.send_message(chat_id, f"🛑 Stopped tracking `{fb_id}`")
            else:
                self.send_message(chat_id, "❌ Profile not found")
        
        elif text.startswith('/history '):
            fb_id = text[9:].strip()
            history = tracker.get_history(fb_id, 10)
            if history:
                msg = f"📋 *History - {fb_id}*\n\n"
                for h in history[:10]:
                    msg += f"`{h['timestamp'][:10]}` - `{h['status']}` ({h['last_seen']})\n"
            else:
                msg = "❌ No history"
            self.send_message(chat_id, msg)
        
        elif 'facebook.com' in text:
            success, msg = tracker.add_target(user_id, text)
            self.send_message(chat_id, msg)
    
    def handle_callback(self, callback):
        chat_id = callback['message']['chat']['id']
        data = callback['data']
        user_id = callback['from']['id']
        
        if data == "add_profile":
            self.send_message(chat_id, "📎 Send Facebook profile URL:\n`https://facebook.com/username`")
        
        elif data == "list_profiles":
            targets = TrackerDB.get_targets(user_id)
            if targets:
                msg = "*Your Profiles:*\n\n"
                for t in targets:
                    status = tracker.get_status(t[0])
                    status_icon = "🟢" if status.get('active') else "⚪"
                    msg += f"{status_icon} *{t[1]}* - `{status.get('status', 'unknown')}`\n"
            else:
                msg = "❌ No profiles tracked"
            self.send_message(chat_id, msg)
        
        elif data == "online_status":
            targets = TrackerDB.get_targets(user_id)
            if targets:
                msg = "*Online Status:*\n\n"
                for t in targets:
                    status = tracker.get_status(t[0])
                    if status.get('status') == 'online':
                        msg += f"🟢 {t[1]} - *ONLINE*\n"
                    else:
                        msg += f"⚪ {t[1]} - `{status.get('last_seen', 'unknown')}`\n"
            else:
                msg = "❌ No profiles tracked"
            self.send_message(chat_id, msg)
        
        elif data == "history":
            self.send_message(chat_id, "📋 Use command: `/history fb_id`")
    
    def run(self):
        logger.info("🚀 Telegram bot polling started")
        while True:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.handle_update(update)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Bot error: {e}")
                time.sleep(5)

def start_bot_thread():
    if TELEGRAM_BOT_TOKEN:
        bot = TelegramBot(TELEGRAM_BOT_TOKEN)
        thread = threading.Thread(target=bot.run, daemon=True)
        thread.start()
    else:
        logger.warning("⚠️ No Telegram token - bot disabled")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("🔍 Facebook Activity Tracker v3.0 - STARTING")
    logger.info("="*80)
    
    if fb_manager.is_logged_in:
        logger.info("✅ Facebook session authenticated")
    else:
        logger.warning("⚠️ Facebook login failed - limited functionality")
    
    start_bot_thread()
    
    logger.info(f"🚀 Flask server on 0.0.0.0:{PORT}")
    logger.info("📡 APIs ready: /api/targets, /api/status, /api/history")
    logger.info("="*80)
    
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)
