from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from src.models.media import MediaFile, SocialMediaPost, SocialMediaAccount, db
from src.models.user import User
from src.services.ai_service import AIService
from src.services.social_media_service import SocialMediaService, ViralTimeService
import os
import uuid
import json
from datetime import datetime

media_bp = Blueprint('media', __name__)

# Initialize services
ai_service = AIService()
social_media_service = SocialMediaService()

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'wmv'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in {'png', 'jpg', 'jpeg', 'gif'}:
        return 'image'
    elif ext in {'mp4', 'avi', 'mov', 'wmv'}:
        return 'video'
    return 'unknown'

@media_bp.route('/media/upload', methods=['POST'])
def upload_media():
    """Upload a media file (image or video)"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id', type=int)
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if file and allowed_file(file.filename):
        # Create upload directory if it doesn't exist
        upload_path = os.path.join(current_app.root_path, UPLOAD_FOLDER)
        os.makedirs(upload_path, exist_ok=True)
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(upload_path, unique_filename)
        
        try:
            # Save file
            file.save(file_path)
            
            # Get file info
            file_size = os.path.getsize(file_path)
            file_type = get_file_type(original_filename)
            
            # Save to database
            media_file = MediaFile(
                user_id=user_id,
                filename=unique_filename,
                original_filename=original_filename,
                file_path=file_path,
                file_type=file_type,
                file_size=file_size,
                mime_type=file.mimetype
            )
            db.session.add(media_file)
            db.session.commit()
            
            return jsonify(media_file.to_dict()), 201
            
        except Exception as e:
            return jsonify({'error': f'Failed to upload file: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@media_bp.route('/media/files', methods=['GET'])
def get_media_files():
    """Get all media files for a user"""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    files = MediaFile.query.filter_by(user_id=user_id).order_by(MediaFile.uploaded_at.desc()).all()
    return jsonify([file.to_dict() for file in files])

@media_bp.route('/media/files/<int:file_id>', methods=['DELETE'])
def delete_media_file(file_id):
    """Delete a media file"""
    media_file = MediaFile.query.get_or_404(file_id)
    
    try:
        # Delete physical file
        if os.path.exists(media_file.file_path):
            os.remove(media_file.file_path)
        
        # Delete from database
        db.session.delete(media_file)
        db.session.commit()
        
        return '', 204
        
    except Exception as e:
        return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500

@media_bp.route('/media/generate-content', methods=['POST'])
def generate_content():
    """Generate hashtags and caption for a media file using AI"""
    data = request.json
    media_file_id = data.get('media_file_id')
    platform = data.get('platform', 'general')
    custom_prompt = data.get('custom_prompt', '')
    
    if not media_file_id:
        return jsonify({'error': 'media_file_id is required'}), 400
    
    media_file = MediaFile.query.get_or_404(media_file_id)
    
    try:
        # Prepare media info for AI service
        media_info = {
            'filename': media_file.original_filename,
            'file_type': media_file.file_type,
            'mime_type': media_file.mime_type
        }
        
        # Generate content using AI service
        content_data = ai_service.generate_social_media_content(media_info, platform, custom_prompt)
        
        return jsonify(content_data)
        
    except Exception as e:
        return jsonify({'error': f'Failed to generate content: {str(e)}'}), 500

@media_bp.route('/media/schedule-post', methods=['POST'])
def schedule_post():
    """Schedule a social media post"""
    data = request.json
    user_id = data.get('user_id')
    media_file_id = data.get('media_file_id')
    platforms = data.get('platforms', [])  # List of platforms
    title = data.get('title', '')
    description = data.get('description', '')
    hashtags = data.get('hashtags', [])
    scheduled_time = data.get('scheduled_time')
    
    if not all([user_id, media_file_id, platforms, scheduled_time]):
        return jsonify({'error': 'user_id, media_file_id, platforms, and scheduled_time are required'}), 400
    
    # Verify user and media file exist
    user = User.query.get(user_id)
    media_file = MediaFile.query.get(media_file_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if not media_file:
        return jsonify({'error': 'Media file not found'}), 404
    if media_file.user_id != user_id:
        return jsonify({'error': 'Access denied to media file'}), 403
    
    try:
        # Parse scheduled time
        scheduled_datetime = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
        
        # Create posts for each platform
        created_posts = []
        for platform in platforms:
            post = SocialMediaPost(
                user_id=user_id,
                media_file_id=media_file_id,
                platform=platform.lower(),
                title=title,
                description=description,
                hashtags=json.dumps(hashtags) if isinstance(hashtags, list) else hashtags,
                scheduled_time=scheduled_datetime
            )
            db.session.add(post)
            created_posts.append(post)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully scheduled {len(created_posts)} posts',
            'posts': [post.to_dict() for post in created_posts]
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Failed to schedule post: {str(e)}'}), 500

@media_bp.route('/media/posts', methods=['GET'])
def get_scheduled_posts():
    """Get all scheduled posts for a user"""
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status')  # Optional filter by status
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    query = SocialMediaPost.query.filter_by(user_id=user_id)
    
    if status:
        query = query.filter_by(status=status)
    
    posts = query.order_by(SocialMediaPost.scheduled_time.desc()).all()
    return jsonify([post.to_dict() for post in posts])

@media_bp.route('/media/posts/<int:post_id>', methods=['DELETE'])
def cancel_post(post_id):
    """Cancel a scheduled post"""
    post = SocialMediaPost.query.get_or_404(post_id)
    
    if post.status != 'scheduled':
        return jsonify({'error': 'Can only cancel scheduled posts'}), 400
    
    post.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'message': 'Post cancelled successfully'})

@media_bp.route('/media/accounts', methods=['GET'])
def get_social_accounts():
    """Get connected social media accounts for a user"""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    accounts = SocialMediaAccount.query.filter_by(user_id=user_id, is_active=True).all()
    return jsonify([account.to_dict() for account in accounts])


@media_bp.route('/media/upload-to-platform', methods=['POST'])
def upload_to_platform():
    """Upload media directly to a social media platform"""
    data = request.json
    media_file_id = data.get('media_file_id')
    platform = data.get('platform')
    access_token = data.get('access_token')
    metadata = data.get('metadata', {})
    
    if not all([media_file_id, platform, access_token]):
        return jsonify({'error': 'media_file_id, platform, and access_token are required'}), 400
    
    # Get media file
    media_file = MediaFile.query.get_or_404(media_file_id)
    
    try:
        # Upload to platform
        result = social_media_service.upload_to_platform(
            platform=platform,
            media_file_path=media_file.file_path,
            metadata=metadata,
            access_token=access_token
        )
        
        if result['success']:
            # Update database with upload result
            post = SocialMediaPost(
                user_id=media_file.user_id,
                media_file_id=media_file_id,
                platform=platform,
                title=metadata.get('title', ''),
                description=metadata.get('description', ''),
                hashtags=json.dumps(metadata.get('hashtags', [])),
                status='published',
                platform_post_id=result.get('post_id') or result.get('video_id') or result.get('media_id'),
                platform_url=result.get('url', ''),
                published_at=datetime.utcnow()
            )
            db.session.add(post)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'platform': platform,
                'result': result,
                'post_id': post.id
            })
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@media_bp.route('/media/schedule-platform-upload', methods=['POST'])
def schedule_platform_upload():
    """Schedule media upload to a social media platform"""
    data = request.json
    media_file_id = data.get('media_file_id')
    platform = data.get('platform')
    access_token = data.get('access_token')
    metadata = data.get('metadata', {})
    scheduled_time = data.get('scheduled_time')
    
    if not all([media_file_id, platform, access_token, scheduled_time]):
        return jsonify({'error': 'media_file_id, platform, access_token, and scheduled_time are required'}), 400
    
    # Get media file
    media_file = MediaFile.query.get_or_404(media_file_id)
    
    try:
        # Parse scheduled time
        scheduled_datetime = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
        
        # Schedule upload
        result = social_media_service.schedule_upload(
            platform=platform,
            media_file_path=media_file.file_path,
            metadata=metadata,
            access_token=access_token,
            scheduled_time=scheduled_datetime
        )
        
        if result['success']:
            # Save scheduled post to database
            post = SocialMediaPost(
                user_id=media_file.user_id,
                media_file_id=media_file_id,
                platform=platform,
                title=metadata.get('title', ''),
                description=metadata.get('description', ''),
                hashtags=json.dumps(metadata.get('hashtags', [])),
                status='scheduled',
                scheduled_time=scheduled_datetime,
                platform_post_id=result.get('scheduled_id')
            )
            db.session.add(post)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'platform': platform,
                'result': result,
                'post_id': post.id
            })
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'error': f'Scheduling failed: {str(e)}'}), 500

@media_bp.route('/media/viral-times/<platform>', methods=['GET'])
def get_viral_times(platform):
    """Get optimal posting times for a platform"""
    timezone = request.args.get('timezone', 'UTC')
    
    try:
        optimal_times = ViralTimeService.get_optimal_times(platform, timezone)
        next_optimal = ViralTimeService.suggest_next_optimal_time(platform, timezone)
        
        return jsonify({
            'platform': platform,
            'timezone': timezone,
            'optimal_times': optimal_times,
            'next_suggested_time': next_optimal.isoformat(),
            'current_time': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get viral times: {str(e)}'}), 500

@media_bp.route('/media/upload-status/<platform>/<upload_id>', methods=['GET'])
def get_upload_status(platform, upload_id):
    """Get upload status from a platform"""
    access_token = request.args.get('access_token')
    
    if not access_token:
        return jsonify({'error': 'access_token is required'}), 400
    
    try:
        result = social_media_service.get_upload_status(platform, upload_id, access_token)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Failed to get status: {str(e)}'}), 500

@media_bp.route('/media/platforms', methods=['GET'])
def get_supported_platforms():
    """Get list of supported social media platforms"""
    platforms = {
        'youtube': {
            'name': 'YouTube',
            'supports_video': True,
            'supports_image': False,
            'supports_scheduling': False,
            'max_video_size': '128GB',
            'max_video_duration': '12 hours',
            'required_scopes': ['https://www.googleapis.com/auth/youtube.upload']
        },
        'instagram': {
            'name': 'Instagram',
            'supports_video': True,
            'supports_image': True,
            'supports_scheduling': False,
            'max_video_size': '4GB',
            'max_video_duration': '60 minutes',
            'required_scopes': ['instagram_business_basic', 'instagram_business_content_publish']
        },
        'facebook': {
            'name': 'Facebook',
            'supports_video': True,
            'supports_image': True,
            'supports_scheduling': True,
            'max_video_size': '10GB',
            'max_video_duration': '240 minutes',
            'required_scopes': ['pages_manage_posts', 'pages_manage_engagement']
        },
        'tiktok': {
            'name': 'TikTok',
            'supports_video': True,
            'supports_image': True,
            'supports_scheduling': False,
            'max_video_size': '4GB',
            'max_video_duration': '10 minutes',
            'required_scopes': ['video.publish']
        }
    }
    
    return jsonify({
        'platforms': platforms,
        'total_platforms': len(platforms)
    })

