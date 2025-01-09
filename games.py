from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import json
import requests
import os

LINE_CHANNEL_ACCESS_TOKEN="ArFAMNAKfeBhLVZAWmXZCWTHM4LGQAuVMlCKjAsodMZzffH0O3Bl2XwwiKSGjIGi7sxLbyVF+qXHU5ecOzNHdbLQ63YnAhXT2oS641rRME5Ngz2nYBYFpnR1u6wn2qL5+HzxYEpEXuuX+ioAne1gfgdB04t89/1O/w1cDnyilFU="

# Flaskアプリケーションの初期化
app = Flask(__name__)

# データベース設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lifegame.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# プレイヤーモデル
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(50), unique=True, nullable=False)
    group_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    position = db.Column(db.Integer, default=0)  # 人生ゲーム上の位置
    balance = db.Column(db.Integer, default=1000)  # 初期資産

# ゲーム状態モデル
class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(50), unique=True, nullable=False)
    current_turn = db.Column(db.Integer, default=0)  # 現在のプレイヤーのターン
    in_progress = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

# LINEからのメッセージに応答
@app.route('/callback', methods=['POST'])
def callback():
    body = request.get_data(as_text=True)
    events = json.loads(body)['events']

    for event in events:
        if event['type'] == 'message' and event['message']['type'] == 'text':
            user_id = event['source']['userId']
            group_id = event['source'].get('groupId', user_id)  # グループか個人を区別
            user_message = event['message']['text']
            reply_token = event['replyToken']

            # メッセージの処理
            reply_message = handle_message(group_id, user_id, user_message)

            # 返信を送信
            send_reply_message(reply_token, reply_message)

    return 'OK'

def handle_message(group_id, user_id, message):
    if message == "ゲーム開始":
        return start_game(group_id)
    elif message == "参加":
        return register_player(group_id, user_id)
    elif message == "状態確認":
        return check_status(group_id, user_id)
    else:
        return "不明なコマンドです。「ゲーム開始」または「参加」と入力してください。"

def start_game(group_id):
    # グループのゲーム状態を取得
    game = Game.query.filter_by(group_id=group_id).first()
    if not game:
        game = Game(group_id=group_id, in_progress=True)
        db.session.add(game)
        db.session.commit()

    players = Player.query.filter_by(group_id=group_id).all()
    if len(players) < 3:
        return "参加者が3人未満です。全員「参加」と入力してください。"

    return "人生ゲームを開始しました！最初のプレイヤーのターンです。"

def register_player(group_id, user_id):
    player = Player.query.filter_by(line_user_id=user_id).first()
    if not player:
        player = Player(line_user_id=user_id, group_id=group_id)
        db.session.add(player)
        db.session.commit()
        return "プレイヤーとして登録しました！"
    elif player.group_id != group_id:
        return "他のグループで既に登録されています。"
    else:
        return "すでにこのグループで参加しています。"

def check_status(group_id, user_id):
    player = Player.query.filter_by(line_user_id=user_id, group_id=group_id).first()
    if player:
        return f"あなたの位置は {player.position} で、資産は {player.balance} ゴールドです。"
    else:
        return "まだゲームに参加していません。「参加」と入力してください。"

def send_reply_message(reply_token, text):
    print(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}' 
    }
    payload = {
        'replyToken': reply_token,
        'messages': [{
            'type': 'text',
            'text': text
        }]
    }
    requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, data=json.dumps(payload))

if __name__ == '__main__':
    app.run(port=3000, debug=True)


