# Nitrotype Team Manager Bot

An automated team management bot for Nitrotype that tracks member activity, monitors race completions, and distributes rewards based on milestones.

## Features

- **Automated Login**: Handles Nitrotype's React-based authentication system
- **Team Monitoring**: Tracks member join/leave events and race completions
- **Milestone Detection**: Automatically detects when members reach race milestones (1K, 5K, 10K, etc.)
- **Reward Distribution**: Sends Nitrotype cash rewards based on achievements
- **Web Dashboard**: Real-time dashboard showing team statistics and member activity
- **Database Logging**: SQLite database to track all activities and member history
- **24/7 Operation**: Designed for continuous monitoring on free hosting platforms

## Project Structure

```
nitrotype-team-manager/
├── main.py              # Main bot application with Flask web interface
├── templates/
│   └── index.html       # Dashboard web interface
├── nitrotype_data.db    # SQLite database (created automatically)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Installation

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/nitrotype-team-manager.git
   cd nitrotype-team-manager
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Chrome WebDriver:**
   - Download ChromeDriver from https://chromedriver.chromium.org/
   - Add to your PATH or place in project directory

4. **Configure credentials:**
   - Edit `main.py` and update the USERNAME and PASSWORD variables
   - For production, use environment variables:
     ```bash
     export NITROTYPE_USERNAME="your_username"
     export NITROTYPE_PASSWORD="your_password"
     ```

5. **Run the application:**
   ```bash
   python main.py
   ```

6. **Access dashboard:**
   - Open http://localhost:5000 in your browser

### Deployment to Render

1. **Connect your GitHub repository to Render**

2. **Set environment variables in Render:**
   - `NITROTYPE_USERNAME`: Your Nitrotype username
   - `NITROTYPE_PASSWORD`: Your Nitrotype password

3. **Use the following build settings:**
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`

4. **Chrome WebDriver setup for Render:**
   The bot automatically configures Chrome options for headless operation on hosting platforms.

## Usage

### Web Dashboard

The web dashboard provides:

- **Team Statistics**: Active member count, total races, rewards distributed
- **Member Table**: Detailed view of each team member's progress
- **Manual Controls**: Buttons to refresh data and run team checks
- **Export Function**: Download team data as CSV

### API Endpoints

- `GET /` - Web dashboard
- `GET /api/dashboard-data` - Get current team data as JSON
- `
