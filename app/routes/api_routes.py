# app/routes/api_routes.py
from flask import Blueprint, jsonify, request
from ..models.click_tracker import ClickTracker
from ..utils.chat_handler import ChatHandler

api = Blueprint('api', __name__)

click_tracker = ClickTracker()
chat_handler = ChatHandler()

@api.route('/update_click', methods=['POST'])
def update_click():
    return click_tracker.update_click(request.json)

@api.route('/chatresponse', methods=['POST'])
def chat_response():
    return chat_handler.handle_chat(request.json, request.args.get('textname'))