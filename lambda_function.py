from datetime import datetime
import json
import os

from package.dateutil.parser import parse
from package.dateutil.relativedelta import relativedelta
import package.requests as requests


TWITTER_API_USER_LOOKUP = "https://api.twitter.com/2/users/by/username/{}"
TWITTER_API_TIMELINE_LOOKUP = "https://api.twitter.com/2/users/{}/tweets"

TWITTER_HEADERS = {"Authorization": "Bearer {}".format(os.environ["twitter_bearer_token"])}

DISCORD_HEADERS = {"Content-Type": "application/json"}


def get_datetime_lower_limit():
    return datetime.utcnow() - relativedelta(minutes=int(os.environ["interval_minutes"]))


def get_twitter_user_info(username):
    user_lookup_params = {"user.fields": "profile_image_url"}
    response = requests.get(
        TWITTER_API_USER_LOOKUP.format(username),
        headers=TWITTER_HEADERS,
        params=user_lookup_params,
    )
    user_data = response.json()["data"]
    return username, user_data["id"], user_data["profile_image_url"]


def get_twitter_timeline(twitter_user_id, exclude_replies=True):
    timeline_lookup_params = {
        "user.fields": "name,username",
        "tweet.fields": "created_at,in_reply_to_user_id",
        "max_results": 10,
    }
    response = requests.get(
        TWITTER_API_TIMELINE_LOOKUP.format(twitter_user_id),
        headers=TWITTER_HEADERS,
        params=timeline_lookup_params,
    )
    timeline_data = response.json()["data"]

    if exclude_replies:
        return [tweet for tweet in timeline_data if "in_reply_to_user_id" not in tweet]

    return timeline_data


def filter_tweets_after(tweets, datetime_lower_limit):
    return [tweet for tweet in tweets if parse(tweet["created_at"]).replace(tzinfo=None) >= datetime_lower_limit]


def post_tweet_to_discord_webhook(tweet_id, twitter_username, twitter_avatar_url):
    payload = {
        "content": "https://twitter.com/{}/status/{}".format(twitter_username, tweet_id),
        "username": twitter_username,
        "avatar_url": twitter_avatar_url,
    }
    requests.post(os.environ["discord_webhook"], headers=DISCORD_HEADERS, json=payload)


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
    users = [get_twitter_user_info(username) for username in event.get("handles", [])]
    for twitter_username, twitter_user_id, twitter_avatar_url in users:
        tweets = filter_tweets_after(
            tweets=get_twitter_timeline(twitter_user_id),
            datetime_lower_limit=get_datetime_lower_limit(),
        )
        for tweet in tweets:
            post_tweet_to_discord_webhook(tweet["id"], twitter_username, twitter_avatar_url)
