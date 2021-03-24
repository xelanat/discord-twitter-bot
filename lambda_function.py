import json
import os

from datetime import datetime
from dateutil import tz
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import package.requests as requests


def lambda_handler(event, context):
    """
    Receives a list of Twitter handles, and posts recent tweets to a Discord Webhook.
        * performs user lookup by username
        * performs user timeline lookup, and gathers tweets that occurred N minutes ago (excludes replies)
            * N should also be the interval at which EventBridge triggers execute
        * posts tweets to Discord Webhook URL
            * content is the URL of the tweet (Discord automatically embeds the tweet)
            * the Discord username is overwritten by the Twitter user's username
            * if available, the Discord avatar is overwritten by the Twitter user's avatar

    Example Input

    {
        "handles": ["twitterhandle1", "twitterhandle2"]
    }

    Example Discord Webhook POST Request

    curl --location --request POST 'https://discord.com/api/webhooks/<discord_server_id>/<discord_webhook_id>' \
    --header 'Content-Type: application/json' \
    --data-raw '{
        "content": "<tweet_url>",
        "username": "<twitter_username>",
        "avatar_url": "<twitter_user_avatar>"
    }'

    """
    datetime_lower_limit = datetime.utcnow().replace(tzinfo=tz.gettz("UTC")) - relativedelta(minutes=int(os.environ["interval_minutes"]))

    for username in event.get("handles", []):
        twitter_headers = {"Authorization": "Bearer {}".format(os.environ["twitter_bearer_token"])}

        user_lookup_params = {"user.fields": "profile_image_url"}
        response = requests.get(
            "https://api.twitter.com/2/users/by/username/{}".format(username),
            headers=twitter_headers,
            params=user_lookup_params,
        )
        user_data = response.json()["data"]

        twitter_user_id = user_data["id"]
        twitter_avatar_url = user_data["profile_image_url"]

        timeline_lookup_params = {"user.fields": "name,username", "tweet.fields": "created_at,in_reply_to_user_id", "max_results": 10}
        response = requests.get(
            "https://api.twitter.com/2/users/{}/tweets".format(twitter_user_id),
            headers=twitter_headers,
            params=timeline_lookup_params,
        )
        timeline_data = response.json()["data"]
        timeline_excluding_replies = [tweet for tweet in timeline_data if "in_reply_to_user_id" not in tweet]

        for tweet in timeline_excluding_replies:
            tweet_created_at = parse(tweet["created_at"])
            tweet_id = tweet["id"]
            if tweet_created_at >= datetime_lower_limit:
                headers = {"Content-Type": "application/json"}
                payload = {
                    "content": "https://twitter.com/{}/status/{}".format(username, tweet_id),
                    "username": username,
                    "avatar_url": twitter_avatar_url,
                }
                requests.post(os.environ["discord_webhook"], headers=headers, data=payload)
