#!/usr/bin/env python3
"""
Nitrotype Team Manager Bot
Automates team management tasks including member tracking, race monitoring, and reward distribution.
"""

import time
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

app = Flask(__name__)

class NitrotypeBot:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.driver = None
        self.is_logged_in = False
        self.setup_driver()
        self.setup_database()
    
    def setup_driver(self):
        """Initialize Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        # Remove headless for debugging, add back for production
        # chrome_options.add_argument("--headless")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print("Chrome driver initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Chrome driver: {e}")
            raise
    
    def setup_database(self):
        """Initialize SQLite database for storing team data"""
        conn = sqlite3.connect('nitrotype_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                races_completed INTEGER DEFAULT 0,
                last_active TEXT,
                join_date TEXT,
                rewards_given INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                member_username TEXT,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    
    def login(self):
        """Login to Nitrotype account"""
        try:
            print(f"Attempting to login as {self.username}...")
            self.driver.get("https://www.nitrotype.com/login")
            
            # Wait for the dynamic form to load
            wait = WebDriverWait(self.driver, 30)
            
            print("Waiting for login form to load...")
            username_field = wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            
            password_field = self.driver.find_element(By.NAME, "password")
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            
            print("Form elements found, filling credentials...")
            
            # Clear and fill fields
            username_field.clear()
            username_field.send_keys(self.username)
            
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Small delay to ensure React state is updated
            time.sleep(1)
            
            print("Submitting login form...")
            login_button.click()
            
            # Wait for redirect or check for successful login
            time.sleep(5)
            
            if "login" not in self.driver.current_url.lower():
                self.is_logged_in = True
                print("Login successful!")
                self.log_activity("login", None, f"Successfully logged in as {self.username}")
                return True
            else:
                print("Login failed - still on login page")
                return False
                
        except TimeoutException:
            print("Timeout waiting for login form")
            return False
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def get_team_data(self):
        """Scrape current team member data"""
        if not self.is_logged_in:
            print("Not logged in. Please login first.")
            return None
        
        try:
            print("Collecting team data...")
            # Navigate to team page (adjust URL as needed)
            self.driver.get("https://www.nitrotype.com/team")
            
            # Wait for team data to load
            wait = WebDriverWait(self.driver, 15)
            # Add selectors for team member elements
            # This will need to be customized based on actual team page structure
            
            team_data = {
                'member_count': 0,
                'members': [],
                'total_races': 0,
                'last_updated': datetime.now().isoformat()
            }
            
            print(f"Team data collected: {team_data['member_count']} members")
            return team_data
            
        except Exception as e:
            print(f"Error collecting team data: {e}")
            return None
    
    def update_member_database(self, team_data):
        """Update local database with current team data"""
        if not team_data:
            return
        
        conn = sqlite3.connect('nitrotype_data.db')
        cursor = conn.cursor()
        
        for member in team_data.get('members', []):
            cursor.execute('''
                INSERT OR REPLACE INTO team_members 
                (username, races_completed, last_active, join_date)
                VALUES (?, ?, ?, ?)
            ''', (
                member.get('username'),
                member.get('races', 0),
                member.get('last_active'),
                member.get('join_date', datetime.now().isoformat())
            ))
        
        conn.commit()
        conn.close()
        print("Database updated with new team data")
    
    def check_milestones(self):
        """Check for members who reached race milestones"""
        conn = sqlite3.connect('nitrotype_data.db')
        cursor = conn.cursor()
        
        milestones = [1000, 5000, 10000, 25000, 50000, 100000]
        milestone_members = []
        
        for milestone in milestones:
            cursor.execute('''
                SELECT username, races_completed FROM team_members 
                WHERE races_completed >= ? AND rewards_given < ?
            ''', (milestone, milestone))
            
            for username, races in cursor.fetchall():
                milestone_members.append({
                    'username': username,
                    'milestone': milestone,
                    'total_races': races
                })
        
        conn.close()
        return milestone_members
    
    def distribute_rewards(self, member_username, amount):
        """Send Nitrotype cash rewards to team member"""
        # This would need to be implemented based on Nitrotype's gifting system
        print(f"Would send ${amount} NT cash to {member_username}")
        self.log_activity("reward_sent", member_username, f"Sent ${amount} NT cash")
        
        # Update database to track rewards given
        conn = sqlite3.connect('nitrotype_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE team_members 
            SET rewards_given = rewards_given + ? 
            WHERE username = ?
        ''', (amount, member_username))
        conn.commit()
        conn.close()
    
    def log_activity(self, action, member_username, details):
        """Log bot activities to database"""
        conn = sqlite3.connect('nitrotype_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_log (timestamp, action, member_username, details)
            VALUES (?, ?, ?, ?)
        ''', (datetime.now().isoformat(), action, member_username, details))
        conn.commit()
        conn.close()
    
    def run_daily_check(self):
        """Main bot cycle - check team status and distribute rewards"""
        print("Starting daily team check...")
        
        if not self.is_logged_in and not self.login():
            print("Failed to login, aborting daily check")
            return False
        
        # Get current team data
        team_data = self.get_team_data()
        if team_data:
            self.update_member_database(team_data)
        
        # Check for milestones and distribute rewards
        milestone_members = self.check_milestones()
        for member_data in milestone_members:
            reward_amount = member_data['milestone'] // 100  # $10 per 1000 races
            self.distribute_rewards(member_data['username'], reward_amount)
        
        print("Daily check completed successfully")
        return True
    
    def get_dashboard_data(self):
        """Get data for web dashboard"""
        conn = sqlite3.connect('nitrotype_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, races_completed, last_active, rewards_given, status 
            FROM team_members 
            ORDER BY races_completed DESC
        ''')
        members = [
            {
                'username': row[0],
                'races': row[1],
                'last_active': row[2],
                'rewards_given': row[3],
                'status': row[4]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.execute('SELECT COUNT(*) FROM team_members WHERE status = "active"')
        active_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(races_completed) FROM team_members')
        total_races = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'members': members,
            'stats': {
                'active_members': active_count,
                'total_races': total_races,
                'last_updated': datetime.now().isoformat()
            }
        }
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("Driver closed successfully")

# Initialize bot instance
bot = None

@app.route('/')
def dashboard():
    """Main dashboard route"""
    return render_template('index.html')

@app.route('/api/dashboard-data')
def api_dashboard_data():
    """API endpoint for dashboard data"""
    global bot
    if bot:
        data = bot.get_dashboard_data()
        return jsonify(data)
    return jsonify({'error': 'Bot not initialized'})

@app.route('/api/run-check', methods=['POST'])
def api_run_check():
    """API endpoint to manually trigger team check"""
    global bot
    if bot:
        success = bot.run_daily_check()
        return jsonify({'success': success})
    return jsonify({'success': False, 'error': 'Bot not initialized'})

@app.route('/ping')
def ping():
    """Keep-alive endpoint for hosting platforms"""
    return jsonify({'status': 'alive', 'timestamp': time.time()})

if __name__ == '__main__':
    # Initialize bot with credentials
    USERNAME = "zyroxx"  # Move to environment variables in production
    PASSWORD = "Largebaboon200!"  # Move to environment variables in production
    
    try:
        print("Initializing Nitrotype Team Manager Bot...")
        bot = NitrotypeBot(USERNAME, PASSWORD)
        
        # Run initial login and check
        if bot.login():
            print("Bot initialized successfully!")
        
        # Start Flask web server
        app.run(host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\nShutting down bot...")
    finally:
        if bot:
            bot.cleanup()
