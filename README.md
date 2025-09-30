# Reader App

A full-stack reading app built with React and Flask that allows users to save, read, and annotate web articles.

## Features

- 📚 Save articles from any URL
- ✨ Clean, distraction-free reading view
- 🖍️ Highlight text and add notes
- 📊 Track reading statistics
- ✅ Mark articles as read/unread
- 🔐 User authentication

## Tech Stack

**Frontend:**
- React
- React Router
- Axios
- CSS3

**Backend:**
- Python/Flask
- SQLAlchemy
- SQLite database
- Flask-CORS
- Trafilatura (article parsing)
- BeautifulSoup4

## Installation

### Backend Setup

1. Navigate to backend folder:
```bash
cd backend
Create virtual environment:
bash
python3 -m venv venv
source venv/bin/activate
Install dependencies:
bash
pip install -r requirements.txt
Run the backend:
bash
python app.py
Backend will run on http://localhost:5001

Frontend Setup
Navigate to frontend folder:
bash
cd frontend
Install dependencies:
bash
npm install
Run the frontend:
bash
npm start
Frontend will run on http://localhost:3000

Usage
Register a new account
Add article URLs using the input form
Click "Read Article" to view in reader mode
Select text to create highlights
Add notes to your highlights
Mark articles as read when finished
License
MIT

