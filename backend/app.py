from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import jwt
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import trafilatura

app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "https://*.vercel.app"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reader.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    articles = db.relationship('Article', backref='user', lazy=True, cascade='all, delete-orphan')

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    author = db.Column(db.String(200))
    published_date = db.Column(db.String(100))
    top_image = db.Column(db.String(500))
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    reading_progress = db.Column(db.Float, default=0.0)
    tags = db.Column(db.String(500))
    highlights = db.relationship('Highlight', backref='article', lazy=True, cascade='all, delete-orphan')

class Highlight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text)
    color = db.Column(db.String(20), default='yellow')
    position = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Helper function to parse article
def parse_article(url):
    try:
        article = NewsArticle(url)
        article.download()
        article.parse()
        
        return {
            'title': article.title,
            'content': article.text,
            'author': ', '.join(article.authors) if article.authors else None,
            'published_date': str(article.publish_date) if article.publish_date else None,
            'top_image': article.top_image
        }
    except Exception as e:
        print(f"Error parsing article: {e}")
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = soup.find('title')
            title = title.text if title else url
            
            content_tags = soup.find_all(['p', 'article'])
            content = ' '.join([tag.get_text() for tag in content_tags[:20]])
            
            return {
                'title': title,
                'content': content,
                'author': None,
                'published_date': None,
                'top_image': None
            }
        except Exception as e2:
            print(f"Fallback parsing failed: {e2}")
            return None

# Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'message': 'Missing required fields'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already exists'}), 400

    password_hash = generate_password_hash(password)
    new_user = User(username=username, email=email, password_hash=password_hash)
    
    db.session.add(new_user)
    db.session.commit()

    token = jwt.encode({'user_id': new_user.id}, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'message': 'User created successfully',
        'token': token,
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email
        }
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid credentials'}), 401

    token = jwt.encode({'user_id': user.id}, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    }), 200

@app.route('/api/articles', methods=['POST'])
@token_required
def save_article(current_user):
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'message': 'URL is required'}), 400

    existing = Article.query.filter_by(user_id=current_user.id, url=url).first()
    if existing:
        return jsonify({'message': 'Article already saved', 'article': article_to_dict(existing)}), 200

    parsed_data = parse_article(url)
    
    if not parsed_data:
        return jsonify({'message': 'Failed to parse article'}), 400

    new_article = Article(
        user_id=current_user.id,
        url=url,
        title=parsed_data['title'],
        content=parsed_data['content'],
        author=parsed_data['author'],
        published_date=parsed_data['published_date'],
        top_image=parsed_data['top_image'],
        tags=data.get('tags', '')
    )

    db.session.add(new_article)
    db.session.commit()

    return jsonify({
        'message': 'Article saved successfully',
        'article': article_to_dict(new_article)
    }), 201

@app.route('/api/articles', methods=['GET'])
@token_required
def get_articles(current_user):
    articles = Article.query.filter_by(user_id=current_user.id).order_by(Article.saved_at.desc()).all()
    return jsonify({
        'articles': [article_to_dict(article) for article in articles]
    }), 200

@app.route('/api/articles/<int:article_id>', methods=['GET'])
@token_required
def get_article(current_user, article_id):
    article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
    
    if not article:
        return jsonify({'message': 'Article not found'}), 404

    return jsonify({'article': article_to_dict(article, include_highlights=True)}), 200

@app.route('/api/articles/<int:article_id>', methods=['PUT'])
@token_required
def update_article(current_user, article_id):
    article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
    
    if not article:
        return jsonify({'message': 'Article not found'}), 404

    data = request.get_json()
    
    if 'is_read' in data:
        article.is_read = data['is_read']
    if 'reading_progress' in data:
        article.reading_progress = data['reading_progress']
    if 'tags' in data:
        article.tags = data['tags']

    db.session.commit()

    return jsonify({
        'message': 'Article updated successfully',
        'article': article_to_dict(article)
    }), 200

@app.route('/api/articles/<int:article_id>', methods=['DELETE'])
@token_required
def delete_article(current_user, article_id):
    article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
    
    if not article:
        return jsonify({'message': 'Article not found'}), 404

    db.session.delete(article)
    db.session.commit()

    return jsonify({'message': 'Article deleted successfully'}), 200

@app.route('/api/articles/<int:article_id>/highlights', methods=['POST'])
@token_required
def add_highlight(current_user, article_id):
    article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
    
    if not article:
        return jsonify({'message': 'Article not found'}), 404

    data = request.get_json()
    text = data.get('text')
    
    if not text:
        return jsonify({'message': 'Highlight text is required'}), 400

    new_highlight = Highlight(
        article_id=article_id,
        text=text,
        note=data.get('note', ''),
        color=data.get('color', 'yellow'),
        position=data.get('position', 0)
    )

    db.session.add(new_highlight)
    db.session.commit()

    return jsonify({
        'message': 'Highlight added successfully',
        'highlight': highlight_to_dict(new_highlight)
    }), 201

@app.route('/api/highlights/<int:highlight_id>', methods=['DELETE'])
@token_required
def delete_highlight(current_user, highlight_id):
    highlight = Highlight.query.get(highlight_id)
    
    if not highlight:
        return jsonify({'message': 'Highlight not found'}), 404

    article = Article.query.filter_by(id=highlight.article_id, user_id=current_user.id).first()
    if not article:
        return jsonify({'message': 'Unauthorized'}), 403

    db.session.delete(highlight)
    db.session.commit()

    return jsonify({'message': 'Highlight deleted successfully'}), 200

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    total_articles = Article.query.filter_by(user_id=current_user.id).count()
    read_articles = Article.query.filter_by(user_id=current_user.id, is_read=True).count()
    total_highlights = Highlight.query.join(Article).filter(Article.user_id == current_user.id).count()

    return jsonify({
        'total_articles': total_articles,
        'read_articles': read_articles,
        'unread_articles': total_articles - read_articles,
        'total_highlights': total_highlights
    }), 200

def article_to_dict(article, include_highlights=False):
    result = {
        'id': article.id,
        'url': article.url,
        'title': article.title,
        'content': article.content,
        'author': article.author,
        'published_date': article.published_date,
        'top_image': article.top_image,
        'saved_at': article.saved_at.isoformat(),
        'is_read': article.is_read,
        'reading_progress': article.reading_progress,
        'tags': article.tags
    }
    
    if include_highlights:
        result['highlights'] = [highlight_to_dict(h) for h in article.highlights]
    
    return result

def highlight_to_dict(highlight):
    return {
        'id': highlight.id,
        'article_id': highlight.article_id,
        'text': highlight.text,
        'note': highlight.note,
        'color': highlight.color,
        'position': highlight.position,
        'created_at': highlight.created_at.isoformat()
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
