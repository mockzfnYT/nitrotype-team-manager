import os
import threading
import time
import json
import random
import logging
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import func
from werkzeug.middleware.proxy_fix import ProxyFix

# For Selenium/Cloudscraper bot features
import requests
from fake_useragent import UserAgent
import cloudscraper
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc
from selenium_stealth import stealth

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

### Flask and SQLAlchemy setup ###
class Base(DeclarativeBase): pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
database_url = os.environ.get("DATABASE_URL", "sqlite:///nitrotype_team.db")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_recycle": 300, "pool_pre_ping": True}
db.init_app(app)

### Models ###
class TeamMember(db.Model):
    __tablename__ = 'team_members'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    last_24_hours = db.Column(db.Integer, default=0)
    this_week = db.Column(db.Integer, default=0)
    total_team_races = db.Column(db.Integer, default=0)
    ntc_owed = db.Column(db.String(20), default='0')
    payment_progress = db.Column(db.String(50), default='--')
    min_requirements_status = db.Column(db.String(100), default='')
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')
    date_joined_left = db.Column(db.String(50), default='')
    rewards_given = db.Column(db.Integer, default=0)
    milestone = db.Column(db.Integer, default=0)
    milestones_reached = db.Column(db.Text, default='[]')

    @property
    def is_new(self):
        return self.join_date and (datetime.utcnow() - self.join_date) <= timedelta(days=1)
    @property
    def recently_left(self):
        return (self.status == 'left' and self.last_seen and (datetime.utcnow() - self.last_seen) <= timedelta(days=1))
    @property
    def profile_url(self):
        return f"https://www.nitrotype.com/racer/{self.username}"
    def __repr__(self): return f'<TeamMember {self.username}>'

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    action = db.Column(db.String(50), nullable=False)
    member_username = db.Column(db.String(100))
    details = db.Column(db.Text)
    def __repr__(self): return f'<ActivityLog {self.action} - {self.member_username}>'

class BotConfig(db.Model):
    __tablename__ = 'bot_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    @staticmethod
    def get_value(key, default=None):
        config = BotConfig.query.filter_by(key=key).first()
        return config.value if config else default
    @staticmethod
    def set_value(key, value):
        config = BotConfig.query.filter_by(key=key).first()
        if config:
            config.value = str(value)
            config.updated_at = datetime.utcnow()
        else:
            config = BotConfig()
            config.key = key
            config.value = str(value)
            db.session.add(config)
        db.session.commit()
    def __repr__(self): return f'<BotConfig {self.key}>'

with app.app_context():
    db.create_all()

### Nitrotype Selenium Bot ###
class NitrotypeTeamBot:
    def __init__(self):
        self.username = os.environ.get("NITROTYPE_USERNAME", "")
        self.password = os.environ.get("NITROTYPE_PASSWORD", "")
        self.driver = None
        self.is_logged_in = False
        self.api_session = None
        self.api_cookies = None
        self.team_page_url = "https://www.nitrotype.com/team"
        self.user_agent = UserAgent()
        self.last_error = None
        self.blocked_status = False

    def setup_driver(self):
        return self._setup_undetected_chrome() or self._setup_stealth_firefox()

    def _setup_undetected_chrome(self):
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'--user-agent={self.get_random_user_agent()}')
            self.driver = uc.Chrome(options=options, headless=True, use_subprocess=False)
            stealth(self.driver, languages=["en-US", "en"], vendor="Google Inc.", platform="Win32",
                    webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
            self._inject_advanced_stealth_scripts()
            return True
        except Exception as e:
            logger.warning(f"Undetected Chrome setup failed: {e}")
            if self.driver:
                try: self.driver.quit()
                except: pass
                self.driver = None
            return False

    def _inject_advanced_stealth_scripts(self):
        if not self.driver: return
        try:
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']})")
            self.driver.execute_script("window.chrome = {runtime: {}};")
        except Exception as e:
            logger.warning(f"Error injecting stealth scripts: {e}")

    def _setup_stealth_firefox(self):
        try:
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--headless")
            firefox_options.add_argument("--no-sandbox")
            firefox_options.add_argument("--disable-dev-shm-usage")
            firefox_options.add_argument("--width=1920")
            firefox_options.add_argument("--height=1080")
            firefox_options.set_preference("dom.webdriver.enabled", False)
            firefox_options.set_preference("useAutomationExtension", False)
            firefox_options.set_preference("general.useragent.override", self.get_random_user_agent())
            service = FirefoxService(executable_path="geckodriver")
            self.driver = webdriver.Firefox(service=service, options=firefox_options)
            self._inject_advanced_stealth_scripts()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize stealth Firefox driver: {e}")
            if self.driver:
                try: self.driver.quit()
                except: pass
                self.driver = None
            return False

    def get_random_user_agent(self):
        try: return self.user_agent.random
        except:
            agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            return random.choice(agents)

    def nitrotype_api_login(self):
        session = requests.Session()
        user_agent = self.get_random_user_agent()
        session.headers.update({
            'origin': 'https://www.nitrotype.com',
            'referer': 'https://www.nitrotype.com/login',
            'user-agent': user_agent,
            'x-username': self.username,
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'accept-encoding': 'gzip, deflate, br',
            'cache-control': 'no-cache',
            'pragma': 'no-cache'
        })
        session.get('https://nitrotype.com/login')
        login_data = {
            'username': self.username,
            'password': self.password,
            'captchaToken': '',
            'authCode': '',
            'trustDevice': False,
            'tz': 'America/Chicago',
        }
        try:
            time.sleep(random.uniform(2, 5))
            session.get('https://www.nitrotype.com/login', timeout=30)
            time.sleep(random.uniform(1, 3))
            response = session.post(
                'https://www.nitrotype.com/api/v2/auth/login/username',
                json=login_data,
                timeout=30
            )
            if response.status_code == 200 and response.json().get('status') == 'OK':
                cookies = session.cookies
                cookies_str = '; '.join([f"{cookie.name}={cookie.value}" for cookie in cookies])
                logger.info("API login successful")
                self.blocked_status = False
                self.last_error = None
                return session, cookies_str
            else:
                error_text = response.text
                logger.error(f"API login failed: {error_text}")
                if "Access denied" in error_text or "1005" in error_text:
                    self.blocked_status = True
                    self.last_error = "Cloudflare blocked access - IP address banned"
                elif "403" in str(response.status_code):
                    self.blocked_status = True
                    self.last_error = "Access forbidden - possible rate limiting or IP block"
                else:
                    self.last_error = f"Login failed: {error_text[:100]}..."
                return None, None
        except Exception as e:
            logger.error(f"API login error: {e}")
            self.last_error = f"Login error: {str(e)}"
            return None, None

    def set_cookies_in_selenium(self, cookies_str):
        if not self.driver: return False
        try:
            self.driver.get("https://www.nitrotype.com/")
            time.sleep(random.uniform(3, 6))
            for cookie in cookies_str.split('; '):
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    cookie_dict = {'name': name, 'value': value, 'domain': 'www.nitrotype.com'}
                    try: self.driver.add_cookie(cookie_dict)
                    except Exception: pass
            self.driver.refresh()
            time.sleep(random.uniform(3, 6))
            return True
        except Exception as e:
            logger.error(f"Error setting cookies with stealth: {e}")
            return False

    def login(self):
        if not self.username or not self.password:
            logger.error("Nitrotype credentials not provided")
            return False
        if not self.setup_driver():
            logger.error("Failed to setup stealth driver")
            return False
        time.sleep(random.uniform(3, 7))
        self.api_session, self.api_cookies = self.nitrotype_api_login()
        if self.api_session and self.api_cookies:
            if self.set_cookies_in_selenium(self.api_cookies):
                self.is_logged_in = True
                self.log_activity("login", None, f"Successfully logged in as {self.username} using stealth")
                logger.info("Stealth login successful!")
                return True
        logger.info("API login failed, trying direct Selenium stealth login...")
        return self._try_direct_selenium_login()

    def _try_direct_selenium_login(self):
        if not self.driver: logger.error("No driver available for direct login"); return False
        try:
            self.driver.get("https://www.nitrotype.com/login")
            time.sleep(random.uniform(3, 6))
            wait = WebDriverWait(self.driver, 20)
            username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
            username_field.send_keys(self.username)
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            password_field.send_keys(self.password)
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            time.sleep(random.uniform(3, 6))
            current_url = self.driver.current_url
            if "login" not in current_url.lower():
                self.is_logged_in = True
                self.log_activity("login", None, f"Direct Selenium stealth login successful for {self.username}")
                logger.info("Direct Selenium stealth login successful!")
                return True
            logger.error("Direct Selenium login failed")
            return False
        except Exception as e:
            logger.error(f"Error in direct Selenium login: {e}")
            return False

    def get_team_data(self):
        if not self.is_logged_in or not self.driver:
            logger.error("Not logged in or driver not available")
            return None
        try:
            self.driver.get(self.team_page_url)
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
            time.sleep(random.uniform(5, 8))
            members = []
            member_elements = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            for elem in member_elements:
                try:
                    cells = elem.find_elements(By.CSS_SELECTOR, "td")
                    if len(cells) < 3: continue
                    cell_texts = [cell.text.strip() for cell in cells]
                    member_data = {
                        'display_name': cell_texts[0] if len(cell_texts) else 'Unknown',
                        'username': cell_texts[1] if len(cell_texts) > 1 else 'unknown',
                        'last_24_hours': self._parse_race_count(cell_texts[2]) if len(cell_texts) > 2 else 0,
                        'this_week': self._parse_race_count(cell_texts[3]) if len(cell_texts) > 3 else 0,
                        'total_team_races': self._parse_race_count(cell_texts[4]) if len(cell_texts) > 4 else 0,
                        'ntc_owed': cell_texts[5] if len(cell_texts) > 5 else '0',
                        'payment_progress': cell_texts[6] if len(cell_texts) > 6 else '--',
                        'min_requirements': cell_texts[7] if len(cell_texts) > 7 else '',
                        'date_joined_left': cell_texts[8] if len(cell_texts) > 8 else ''
                    }
                    members.append(member_data)
                except Exception as e:
                    logger.warning(f"Error processing member row: {e}")
                    continue
            team_data = {
                'member_count': len(members),
                'members': members,
                'total_races': sum(m.get('total_team_races', 0) for m in members),
                'last_updated': datetime.utcnow().isoformat()
            }
            return team_data
        except Exception as e:
            logger.error(f"Error collecting team data: {e}")
            return None

    def _parse_race_count(self, text):
        if not text or text == '--': return 0
        clean_text = text.replace('Races', '').replace('races', '').replace(',', '').strip()
        try: return int(clean_text)
        except ValueError: return 0

    def update_member_database(self, team_data):
        if not team_data or not team_data.get('members'): logger.warning("No team data to update"); return
        with app.app_context():
            try:
                current_members = {member.username: member for member in TeamMember.query.all()}
                new_usernames = {m['username'] for m in team_data['members']}
                old_usernames = set(current_members.keys())
                joined = new_usernames - old_usernames
                left = old_usernames - new_usernames
                stayed = new_usernames & old_usernames
                for username in joined:
                    member_data = next(m for m in team_data['members'] if m['username'] == username)
                    new_member = TeamMember(
                        username=username,
                        display_name=member_data.get('display_name', username),
                        last_24_hours=member_data.get('last_24_hours', 0),
                        this_week=member_data.get('this_week', 0),
                        total_team_races=member_data.get('total_team_races', 0),
                        ntc_owed=member_data.get('ntc_owed', '0'),
                        payment_progress=member_data.get('payment_progress', '--'),
                        min_requirements_status=member_data.get('min_requirements', ''),
                        date_joined_left=member_data.get('date_joined_left', ''),
                        status='new',
                        join_date=datetime.utcnow(),
                        last_seen=datetime.utcnow()
                    )
                    db.session.add(new_member)
                    self.log_activity("member_joined", username, f"New member joined: {member_data.get('display_name', username)}")
                for username in left:
                    member = current_members[username]
                    member.status = 'left'
                    member.last_seen = datetime.utcnow()
                    self.log_activity("member_left", username, f"Member left team: {member.display_name}")
                for username in stayed:
                    member_data = next(m for m in team_data['members'] if m['username'] == username)
                    member = current_members[username]
                    old_total = member.total_team_races
                    new_total = member_data.get('total_team_races', 0)
                    member.display_name = member_data.get('display_name', member.display_name)
                    member.last_24_hours = member_data.get('last_24_hours', 0)
                    member.this_week = member_data.get('this_week', 0)
                    member.total_team_races = new_total
                    member.ntc_owed = member_data.get('ntc_owed', '0')
                    member.payment_progress = member_data.get('payment_progress', '--')
                    member.min_requirements_status = member_data.get('min_requirements', '')
                    member.date_joined_left = member_data.get('date_joined_left', member.date_joined_left)
                    if new_total != old_total:
                        self.log_activity("races_updated", username, f"Total races: {old_total} → {new_total}")
                    member.last_seen = datetime.utcnow()
                    if member.status == 'left':
                        member.status = 'active'
                        self.log_activity("member_returned", username, f"Member returned to team")
                for member in TeamMember.query.filter_by(status='new').all():
                    if not member.is_new: member.status = 'active'
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating database: {e}")

    def check_milestones_and_distribute_rewards(self):
        milestones = [1000, 5000, 10000, 25000, 50000, 100000]
        with app.app_context():
            try:
                for member in TeamMember.query.filter_by(status='active').all():
                    reached_milestones = json.loads(member.milestones_reached) if member.milestones_reached else []
                    for milestone in milestones:
                        if (member.total_team_races >= milestone and milestone not in reached_milestones):
                            reward_amount = milestone // 100
                            reached_milestones.append(milestone)
                            member.milestones_reached = json.dumps(reached_milestones)
                            member.rewards_given += reward_amount
                            member.milestone = milestone
                            self.log_activity(
                                "milestone_reached", member.username,
                                f"Reached {milestone:,} races! Reward: ${reward_amount} NTC"
                            )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error checking milestones: {e}")

    def log_activity(self, action, member_username, details):
        with app.app_context():
            try:
                activity = ActivityLog(action=action, member_username=member_username, details=details, timestamp=datetime.utcnow())
                db.session.add(activity)
                db.session.commit()
            except Exception as e: logger.error(f"Error logging activity: {e}")

    def run_team_check(self):
        logger.info("Starting team check...")
        try:
            with app.app_context():
                BotConfig.set_value('bot_status', 'running')
                BotConfig.set_value('last_attempt', datetime.utcnow().isoformat())
            if not self.is_logged_in:
                if not self.login():
                    logger.error("Failed to login.")
                    with app.app_context():
                        BotConfig.set_value('bot_status', 'login_failed')
                        BotConfig.set_value('last_error', self.last_error or 'Login failed')
                    return False
            team_data = self.get_team_data()
            if not team_data:
                logger.error("Failed to get team data")
                with app.app_context():
                    BotConfig.set_value('bot_status', 'data_fetch_failed')
                return False
            self.update_member_database(team_data)
            self.check_milestones_and_distribute_rewards()
            with app.app_context():
                BotConfig.set_value('last_check', datetime.utcnow().isoformat())
                BotConfig.set_value('bot_status', 'success')
                BotConfig.set_value('last_error', '')
            logger.info("Team check completed successfully")
            self.blocked_status = False
            self.last_error = None
            return True
        except Exception as e:
            error_msg = f"Error during team check: {e}"
            logger.error(error_msg)
            self.last_error = str(e)
            with app.app_context():
                BotConfig.set_value('bot_status', 'error')
                BotConfig.set_value('last_error', str(e))
            return False
        finally: self.cleanup()

    def cleanup(self):
        if self.driver:
            try: self.driver.quit()
            except Exception as e: logger.error(f"Error closing driver: {e}")
        self.driver = None
        self.is_logged_in = False

### Flask routes ###
@app.route('/')
def index():
    try:
        with app.app_context():
            total_members = TeamMember.query.count()
            active_members = TeamMember.query.filter_by(status='active').count()
            new_members = TeamMember.query.filter(
                TeamMember.status == 'new',
                TeamMember.join_date >= datetime.utcnow() - timedelta(days=1)
            ).count()
            recently_left = TeamMember.query.filter(
                TeamMember.status == 'left',
                TeamMember.last_seen >= datetime.utcnow() - timedelta(days=1)
            ).count()
            total_races = db.session.query(func.sum(TeamMember.total_team_races)).scalar() or 0
            members = TeamMember.query.order_by(TeamMember.total_team_races.desc()).all()
            recent_activity = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(10).all()
            last_check = BotConfig.get_value('last_check')
            last_check_time = None
            if last_check:
                try: last_check_time = datetime.fromisoformat(last_check)
                except Exception: last_check_time = None
            return render_template('index.html',
                total_members=total_members,
                active_members=active_members,
                new_members=new_members,
                recently_left=recently_left,
                total_races=total_races,
                members=members,
                recent_activity=recent_activity,
                last_check_time=last_check_time
            )
    except Exception as e:
        logger.error(f"Error in dashboard: {e}")
        return "Error loading dashboard", 500

@app.route('/api/dashboard-data', methods=['GET'])
def api_dashboard_data():
    try:
        with app.app_context():
            members = TeamMember.query.order_by(TeamMember.total_team_races.desc()).all()
            members_json = [
                {
                    "username": m.username,
                    "display_name": m.display_name,
                    "races": m.total_team_races,
                    "last_active": m.last_seen.isoformat() if m.last_seen else None,
                    "rewards_given": m.rewards_given,
                    "status": m.status,
                    "milestone": m.milestone,
                    "join_date": m.join_date.isoformat() if m.join_date else None,
                    "last_24_hours": m.last_24_hours,
                    "this_week": m.this_week,
                    "ntc_owed": m.ntc_owed,
                    "payment_progress": m.payment_progress,
                    "min_requirements_status": m.min_requirements_status,
                    "date_joined_left": m.date_joined_left
                }
                for m in members
            ]
            stats = {
                "active_members": TeamMember.query.filter_by(status='active').count(),
                "total_members": TeamMember.query.count(),
                "total_races": db.session.query(func.sum(TeamMember.total_team_races)).scalar() or 0,
            }
            return jsonify({
                "members": members_json,
                "stats": stats
            })
    except Exception as e:
        logger.error(f"Error in dashboard-data API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/run-check', methods=['POST'])
def api_run_check():
    try:
        def run_check():
            bot = NitrotypeTeamBot()
            bot.run_team_check()
        thread = threading.Thread(target=run_check)
        thread.start()
        BotConfig.set_value('last_check', datetime.utcnow().isoformat())
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in run-check API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/ping')
def ping():
    return jsonify({'status': 'alive', 'timestamp': time.time()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
