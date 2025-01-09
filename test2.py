from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import json
import requests
import os
import openai
import random
from PIL import Image, ImageDraw
from dotenv import load_dotenv

# .env ファイルの読み込み
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
        if event['type'] == 'message':
            if event['message']['type'] == 'text':  # テキストメッセージ
                user_id = event['source']['userId']
                group_id = event['source'].get('groupId', user_id)
                user_message = event['message']['text']
                reply_token = event['replyToken']

                # メッセージの内容を処理
                if "サイコロ" in user_message or "マス" in user_message:
                    roll_dice_and_update_position(group_id, user_id, reply_token)
                else:
                    reply_message = handle_message(group_id, user_id, user_message)
                    send_reply_message(reply_token, reply_message)

    return 'OK'


def handle_message(group_id, user_id, message):
    #print(f"Received message: {message}")
    if message == "ゲーム開始":
        return start_game(group_id)
    elif message == "参加":
        return register_player(group_id, user_id)
    elif message == "状態確認":
        return check_status(group_id, user_id)
    #変更:GameMaster用と通常のgpt
    elif "サイコロ" in message or "マス" in message: #サイコロを振る処理
        return roll_dice_and_update_position(group_id, user_id)
    elif message == "マップ":  # ユーザーが「マップ」と入力
        return "map"  # 特定のフラグを返す
    else:
        return query_gpt(message)

def handle_location(group_id, user_id, latitude, longitude):
    player = Player.query.filter_by(line_user_id=user_id, group_id=group_id).first()
    if player:
        # サイコロの結果を計算
        dice_roll = int((latitude + longitude) * 100) % 6 + 1  # サイコロの目（1～6）
        player.position += dice_roll  # プレイヤーの位置を更新
        player.position = min(player.position, 70)  # ゴールを超えないように制限

        # GPTにイベント内容を生成させる
        gpt_message = generate_gpt_event_message(player.position, dice_roll)

        db.session.commit()

        return gpt_message
    else:
        return "まだゲームに参加していません。「参加」と入力してください。"

def check_status(group_id, user_id):
    game = Game.query.filter_by(group_id=group_id).first()
    players = Player.query.filter_by(group_id=group_id).order_by(Player.id).all()

    if not game or not players:
        return "ゲームが開始されていないか、参加者がいません。"

    current_player = players[game.current_turn]
    player_status = [
        f"{player.name if player.name else 'プレイヤー'}: {player.position}マス目で,資産:{player.balance} ゴールドです。"
        for player in players
    ]
    status_message = "\n".join(player_status)
    return f"現在のターン: {current_player.name} さん\n{status_message}"
    
def start_game(group_id):
    game = Game.query.filter_by(group_id=group_id).first()
    if not game:
        game = Game(group_id=group_id, in_progress=True)
        db.session.add(game)

    players = Player.query.filter_by(group_id=group_id).all()
    if len(players) < 2:
        return "参加者が2人未満です。全員「参加」と入力してください。"

    game.current_turn = 0  # 最初のプレイヤーに設定
    db.session.commit()
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

# GPTにイベント内容を生成させる関数
def generate_gpt_event_message(position, dice_roll):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    prompt = (
        f"プレイヤーが人生ゲームでサイコロを振り、{dice_roll}マス進みました。現在の位置は{position}マス目です。\n"
        "以下のルールに基づき、進行状況を説明し、イベントを生成してください:\n"
        "1. 白マス: 「なにもなかった」と返信。\n"
        "2. 赤マス: プラスの出来事をエピソード付きで通知（例: +50,00円）。\n"
        "3. 青マス: マイナスの出来事をエピソード付きで通知（例: -3,000円）。\n"
        "4. 緑マス: プレイヤーを1から6のランダムな数字分戻してください。\n"
        "※金額範囲は -50,000円 ~ +50,000円。\n"
        "ゴール到達時は特別なメッセージを出力してください。"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたは人生ゲームのゲームマスターです。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error in GPT event generation: {e}")
        return "イベント生成中にエラーが発生しました。"

def generate_map_with_position(position):
    # 元のマップ画像を読み込み
    map_image_path = "map.png"  # マップ画像のパス
    output_image_path = "current_map.png"  # 現在地を示す画像の保存先

    # 画像を開く
    base_image = Image.open(map_image_path).convert("RGBA")

    # 描画用のオーバーレイを作成
    overlay = Image.new("RGBA", base_image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # 現在地の座標を計算（例: マスの座標を事前に定義しておく）
    positions = [
        (50, 50), (100, 50), (150, 50),  # 例: 各マスの座標を設定
        (200, 50), (250, 50), (300, 50)
    ]
    if position < len(positions):
        x, y = positions[position]  # 現在地の座標を取得
        # 現在地を赤い円で描画
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(255, 0, 0, 255))

    # 元の画像とオーバーレイを合成
    combined = Image.alpha_composite(base_image, overlay)
    combined = combined.convert("RGB")  # JPEGで保存するためにRGBに変換
    combined.save(output_image_path, "JPEG")
    return output_image_path

# サイコロを振り、位置を更新
def roll_dice_and_update_position(group_id, user_id, reply_token):
    game = Game.query.filter_by(group_id=group_id).first()
    if not game or not game.in_progress:
        return "ゲームが開始されていません。「ゲーム開始」と入力してください。"

    # プレイヤーリストを取得し、順番を管理
    players = Player.query.filter_by(group_id=group_id).order_by(Player.id).all()
    if not players:
        return "このグループに参加しているプレイヤーがいません。「参加」と入力してください。"

    # 現在のターンのプレイヤーを取得
    current_player = players[game.current_turn]
    if current_player.line_user_id != user_id:
        return f"現在のターンは {current_player.name if current_player.name else 'プレイヤー'} さんです。あなたのターンではありません。"

    # サイコロの結果を生成
    dice_roll = random.randint(1, 6)
    current_player.position += dice_roll
    current_player.position = min(current_player.position, 70)  # ゴールを超えないよう制限

    # マップ画像を動的に生成
    map_image_path = generate_map_with_position(current_player.position)

    # GPTにイベント内容を生成させる
    gpt_message = generate_gpt_event_message(current_player.position, dice_roll)

    # ゴール判定
    if current_player.position == 70:
        gpt_message += f"\n{current_player.name if current_player.name else 'プレイヤー'} さんがゴールに到達しました！おめでとうございます！"

    # 次のターンへ
    game.current_turn = (game.current_turn + 1) % len(players)
    next_player = players[game.current_turn]  # 次のプレイヤー
    db.session.commit()

    # 次のプレイヤー情報を付加して返信
    gpt_message += f"\n次のターンは {next_player.name if next_player.name else 'プレイヤー'} さんです。"

    # 現在地のマップ画像を送信
    send_reply_message(reply_token, gpt_message, f"file://{map_image_path}")  # 生成された画像を送信



def query_gpt(user_message):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        # GPT API 呼び出し
        response = openai.ChatCompletion.create(
            model="gpt-4",  # または "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=100,
            temperature=0.7
        )
        # GPT 応答を抽出して返す
        return response['choices'][0]['message']['content']
    except Exception as e:
        # すべての例外をキャッチしてエラー内容を記録
        print(f"Error in GPT communication: {e}")
        return f"GPTとの通信でエラーが発生しました: {str(e)}"


def send_reply_message(reply_token, text, image_url=None):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }

    messages = [{'type': 'text', 'text': text}]
    
    if image_url:
        messages.append({
            'type': 'image',
            'originalContentUrl': "https://drive.google.com/uc?id=1RlnstY0ZJoU5Z5V51UXUUb0g0n5hXBq5",  # 画像のURL
            'previewImageUrl': "https://drive.google.com/uc?id=1RlnstY0ZJoU5Z5V51UXUUb0g0n5hXBq5"      # サムネイル（同じURLを使用可能）
        })

    payload = {
        'replyToken': reply_token,
        'messages': messages
    }

    requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, data=json.dumps(payload))


if __name__ == '__main__':
    app.run(port=3000, debug=True)
