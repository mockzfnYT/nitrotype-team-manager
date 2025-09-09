# [NTFAM] Nitrotype Family - Team Dashboard

This project is an advanced Nitrotype team management dashboard powered by Flask, SQLAlchemy, Selenium, and anti-bot techniques.  
It tracks member stats, milestones, rewards, team activity, and offers a modern Bootstrap dashboard UI.

## Features

- **Automatic Nitrotype login** via Selenium and API with advanced anti-detection
- **Cloudflare bypass** strategies
- **Team member scraping** and milestone tracking
- **Reward calculation** and logging
- **Dashboard** with live stats, activity log, refresh and manual check
- **Bootstrap & FontAwesome** UI

## Setup

1. **Clone repo**

   ```bash
   git clone https://github.com/mockzfnYT/nitrotype-team-manager.git
   cd nitrotype-team-manager
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**

   - `NITROTYPE_USERNAME` – Your Nitrotype account username
   - `NITROTYPE_PASSWORD` – Your Nitrotype account password
   - `SESSION_SECRET` – (optional) Flask session secret
   - `DATABASE_URL` – (optional) DB connection string

4. **Run the app**

   ```bash
   python main.py
   ```

5. **Open dashboard**

   - Visit [http://localhost:5000](http://localhost:5000) in your browser.

## Deployment

- **Render, Heroku, or any cloud platform:**  
  - Add your environment variables in the dashboard
  - Make sure geckodriver/chromedriver is available if using Selenium

## File Structure

- `main.py` – All backend logic, models, bot, routes, and Flask app
- `templates/index.html` – Dashboard UI
- `requirements.txt` – Dependencies
- `.gitignore` – Recommended files to exclude

## FAQ

- **Cloudflare blocking?**  
  See dashboard alert for solutions: try VPN, AWS API Gateway, or deploy on another platform/IP.

- **Add new features or change UI?**  
  Edit `main.py` for backend logic, `index.html` for dashboard appearance.

## Credits

Created by [mockzfnYT](https://github.com/mockzfnYT)
