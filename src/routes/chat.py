from flask import Blueprint, jsonify, request
from src.models.chat import ChatMessage, ChatSession, db
from src.models.user import User
from src.services.ai_service import AIService

chat_bp = Blueprint('chat', __name__)

# Initialize AI service
ai_service = AIService()

@chat_bp.route('/chat/sessions', methods=['GET'])
def get_chat_sessions():
    """Get all chat sessions for a user"""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    sessions = ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.updated_at.desc()).all()
    return jsonify([session.to_dict() for session in sessions])

@chat_bp.route('/chat/sessions', methods=['POST'])
def create_chat_session():
    """Create a new chat session"""
    data = request.json
    user_id = data.get('user_id')
    session_name = data.get('session_name', 'New Chat')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    session = ChatSession(user_id=user_id, session_name=session_name)
    db.session.add(session)
    db.session.commit()
    
    return jsonify(session.to_dict()), 201

@chat_bp.route('/chat/sessions/<int:session_id>', methods=['GET'])
def get_chat_session(session_id):
    """Get a specific chat session with its messages"""
    session = ChatSession.query.get_or_404(session_id)
    
    # Get messages for this session
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    
    session_data = session.to_dict()
    session_data['messages'] = [message.to_dict() for message in messages]
    
    return jsonify(session_data)

@chat_bp.route('/chat/sessions/<int:session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    """Delete a chat session and all its messages"""
    session = ChatSession.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    return '', 204

@chat_bp.route('/chat/message', methods=['POST'])
def send_message():
    """Send a message to the AI chatbot and get a response"""
    data = request.json
    user_id = data.get('user_id')
    session_id = data.get('session_id')
    message = data.get('message')
    
    if not all([user_id, session_id, message]):
        return jsonify({'error': 'user_id, session_id, and message are required'}), 400
    
    # Verify session exists and belongs to user
    session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session:
        return jsonify({'error': 'Session not found or access denied'}), 404
    
    try:
        # Get conversation history for context
        previous_messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).limit(10).all()
        
        # Build conversation context
        conversation_history = []
        for prev_msg in previous_messages:
            conversation_history.append({"role": "user", "content": prev_msg.message})
            conversation_history.append({"role": "assistant", "content": prev_msg.response})
        
        # Get AI response using AI service
        ai_response = ai_service.get_chat_response(message, conversation_history)
        
        # Save the message and response to database
        chat_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            message=message,
            response=ai_response
        )
        db.session.add(chat_message)
        
        # Update session timestamp
        session.updated_at = db.func.now()
        db.session.commit()
        
        return jsonify({
            'message': chat_message.to_dict(),
            'response': ai_response
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get AI response: {str(e)}'}), 500

@chat_bp.route('/chat/messages/<int:session_id>', methods=['GET'])
def get_chat_messages(session_id):
    """Get all messages for a specific chat session"""
    # Verify session exists
    session = ChatSession.query.get_or_404(session_id)
    
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    return jsonify([message.to_dict() for message in messages])

