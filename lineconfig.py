import base64
import hashlib
import hmac

CHANNELSECRET='7855c56ecdd1d8d1acd241c6c0250407'
CHANNELACCESSTOKEN='ArFAMNAKfeBhLVZAWmXZCWTHM4LGQAuVMlCKjAsodMZzffH0O3Bl2XwwiKSGjIGi7sxLbyVF+qXHU5ecOzNHdbLQ63YnAhXT2oS641rRME5Ngz2nYBYFpnR1u6wn2qL5+HzxYEpEXuuX+ioAne1gfgdB04t89/1O/w1cDnyilFU='
BROADCASTAPIURL='https://api.line.me/v2/bot/message/broadcast'
PUSHAPIURL='https://api.line.me/v2/bot/message/push'
MULTICASTAPIURL='https://api.line.me/v2/bot/message/multicast'
REPLYAPIURL='https://api.line.me/v2/bot/message/reply'
DATAAPIURL='https://api-data.line.me/v2/bot/message' # /{messageId}/content'

def validate_signature(body,signature):
    hash = hmac.new(CHANNELSECRET.encode('utf-8'),
        body.encode('utf-8'), hashlib.sha256).digest()
    return  base64.b64encode(hash) == signature.encode('utf-8')
