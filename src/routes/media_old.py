from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from src.models.media import MediaFile, SocialMediaPost, SocialMediaAccount, db
from src.models.user import User
from src.services.ai_service import AIService
import os
import uuid
import json
from datetime import datetime

media_bp = Blueprint('media', __name__)

# Initialize AI service
ai_service = AIService()

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
        # Create prompt based on file type and platform
        base_prompt = f"""
        Generate engaging social media content for a {media_file.file_type} file named "{media_file.original_filename}" 
        that will be posted on {platform}. 
        
        Please provide:
        1. A compelling caption/description (appropriate length for {platform})
        2. Relevant hashtags (trending and niche-specific)
        3. Suggested posting time for maximum engagement
        
        {f"Additional context: {custom_prompt}" if custom_prompt else ""}
        
        Format the response as JSON with keys: caption, hashtags (array), suggested_time
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a social media expert who creates viral content. Always respond with valid JSON."},
                {"role": "user", "content": base_prompt}
            ],
            max_tokens=800,
            temperature=0.8
        )
        
        ai_response = response.choices[0].message.content
        
        # Try to parse JSON response
        import json
        try:
            content_data = json.loads(ai_response)
        except json.JSONDecodeError:
            # Fallback if AI doesn't return valid JSON
            content_data = {
                "caption": ai_response[:500],
                "hashtags": ["#viral", "#trending", "#content"],
                "suggested_time": "Peak hours: 7-9 PM"
            }
        
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

