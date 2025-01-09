from flask import Flask, request
import requests
import json
import hashlib
import hmac
import base64

app = Flask(__name__)

# メッセージを記録する辞書（ユーザーごとにメッセージを蓄積）
user_messages = {}

# LINEの署名検証関数
def validate_signature(payload, signature):
    channel_secret = 'YOUR_CHANNEL_SECRET'  # LINE Developersで取得したチャンネルシークレット
    hash = hmac.new(channel_secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(hash).decode('utf-8') == signature

@app.route('/callback', methods=['POST'])
def response():
    posted_data = request.data
    posted_object = json.loads(posted_data.decode('utf8'))
    response_to_line = ''

    print("=request from LINE Messaging API")
    print(request.data)
    print("---")
    print(posted_object)

    # LINE Messaging API からの POST かを確認
    signature = request.headers.get('x-line-signature', '')
    if not validate_signature(request.get_data(as_text=True), signature):
        print("signature mismatch")
        return response_to_line

    # LINEユーザーIDを取得
    user_id = posted_object['events'][0]['source']['userId']

    # ユーザーの送信メッセージを取得
    user_message = posted_object['events'][0]['message']['text']

    # ユーザーごとのメッセージリストを更新
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(user_message)

    # 現在のメッセージ履歴を繋げて返信メッセージを作成
    concatenated_message = '\n'.join(user_messages[user_id]) + ' やねん'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': "Bearer YOUR_CHANNEL_ACCESS_TOKEN"  # LINE Developersで取得したチャンネルアクセストークン
    }

    payload = {
        'replyToken': posted_object['events'][0]['replyToken'],
        'messages': [{
            'type': 'text',
            'text': concatenated_message
        }]
    }

    print("=request to LINE Messaging API")
    print(payload)

    response = requests.post('https://api.line.me/v2/bot/message/reply', data=json.dumps(payload), headers=headers)
    print("=response from LINE Messaging API")
    print(response.status_code)
    print(response.text)

    return ''

# お約束
if __name__ == '__main__':
    print("afo")
    allowed_host = '0.0.0.0'
    server_port = 3000
    app.debug = True
    app.run(host=allowed_host, port=server_port)