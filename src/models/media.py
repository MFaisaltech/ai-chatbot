from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from src.models.user import db

class MediaFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # 'image' or 'video'
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to social media posts
    posts = db.relationship('SocialMediaPost', backref='media_file', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<MediaFile {self.filename}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'uploaded_at': self.uploaded_at.isoformat()
        }

class SocialMediaPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_file_id = db.Column(db.Integer, db.ForeignKey('media_file.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)  # 'youtube', 'instagram', 'facebook', 'tiktok'
    title = db.Column(db.String(500))
    description = db.Column(db.Text)
    hashtags = db.Column(db.Text)  # JSON string of hashtags
    scheduled_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), default='scheduled')  # 'scheduled', 'posted', 'failed', 'cancelled'
    post_id = db.Column(db.String(200))  # ID from the social media platform after posting
    posted_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SocialMediaPost {self.id} - {self.platform}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'media_file_id': self.media_file_id,
            'platform': self.platform,
            'title': self.title,
            'description': self.description,
            'hashtags': self.hashtags,
            'scheduled_time': self.scheduled_time.isoformat(),
            'status': self.status,
            'post_id': self.post_id,
            'posted_at': self.posted_at.isoformat() if self.posted_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class SocialMediaAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)  # 'youtube', 'instagram', 'facebook', 'tiktok'
    account_name = db.Column(db.String(200))
    access_token = db.Column(db.Text)  # Encrypted access token
    refresh_token = db.Column(db.Text)  # Encrypted refresh token
    token_expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    connected_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<SocialMediaAccount {self.platform} - {self.account_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'platform': self.platform,
            'account_name': self.account_name,
            'is_active': self.is_active,
            'connected_at': self.connected_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None
        }

