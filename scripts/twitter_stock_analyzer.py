import tweepy
import sys
import os
from datetime import datetime, timezone, timedelta

BEARER_TOKEN = os.environ.get('TWITTER_BEARER_TOKEN', '')
if not BEARER_TOKEN:
    print("ERROR: Set TWITTER_BEARER_TOKEN environment variable.")
    print("  export TWITTER_BEARER_TOKEN=your_token_here")
    sys.exit(1)

MAX_TWEETS = 100
DAYS_BACK = 7


def calculate_quality_score(tweet, author):
    """Calculate quality score for each tweet. Good = real data + high engagement."""
    metrics = tweet.public_metrics
    likes = metrics.get('like_count', 0)
    retweets = metrics.get('retweet_count', 0)
    replies = metrics.get('reply_count', 0)

    score = likes + (retweets * 3) + (replies * 2)

    followers = 0
    if author and author.public_metrics:
        followers = author.public_metrics.get('followers_count', 0)

    if followers > 50000:
        score = int(score * 1.5)
    elif followers > 10000:
        score = int(score * 1.2)

    if author and author.verified:
        score = int(score * 1.3)

    text = tweet.text
    if any(char.isdigit() for char in text):
        score = int(score * 1.2)
    if '%' in text:
        score = int(score * 1.1)

    return score


def is_low_quality(tweet):
    """Filter weak tweets — less than 5 likes and 2 retweets."""
    metrics = tweet.public_metrics
    likes = metrics.get('like_count', 0)
    retweets = metrics.get('retweet_count', 0)
    return likes < 5 and retweets < 2


def search_stock_tweets(ticker):
    """Search Twitter for stock tweets. Returns up to 100 quality tweets from last 7 days."""
    client = tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=True)
    query = f"${ticker} lang:en -is:retweet -is:reply"

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=DAYS_BACK)

    print(f"Searching Twitter for ${ticker} — last {DAYS_BACK} days, max {MAX_TWEETS} tweets...")

    all_tweets = []

    try:
        paginator = tweepy.Paginator(
            client.search_recent_tweets,
            query=query,
            tweet_fields=['created_at', 'public_metrics', 'author_id', 'text'],
            user_fields=['name', 'username', 'verified', 'public_metrics'],
            expansions=['author_id'],
            max_results=100,
            start_time=start_time,
            end_time=end_time
        )

        for page in paginator:
            if not page.data:
                continue

            users = {}
            if page.includes and 'users' in page.includes:
                for user in page.includes['users']:
                    users[user.id] = user

            for tweet in page.data:
                author = users.get(tweet.author_id)

                if is_low_quality(tweet):
                    continue

                metrics = tweet.public_metrics
                quality_score = calculate_quality_score(tweet, author)

                all_tweets.append({
                    'text': tweet.text,
                    'created_at': str(tweet.created_at),
                    'likes': metrics.get('like_count', 0),
                    'retweets': metrics.get('retweet_count', 0),
                    'replies': metrics.get('reply_count', 0),
                    'impressions': metrics.get('impression_count', 0),
                    'quality_score': quality_score,
                    'author_name': author.name if author else 'Unknown',
                    'author_username': author.username if author else 'Unknown',
                    'author_verified': author.verified if author else False,
                    'author_followers': author.public_metrics.get('followers_count', 0) if author and author.public_metrics else 0
                })

            if len(all_tweets) >= MAX_TWEETS:
                all_tweets = all_tweets[:MAX_TWEETS]
                break

    except tweepy.TooManyRequests:
        print("Rate limit hit — using tweets collected so far.")
    except tweepy.TwitterServerError as e:
        print(f"Twitter API error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

    all_tweets.sort(key=lambda x: x['quality_score'], reverse=True)
    return all_tweets


def print_results(ticker, tweets):
    """Print tweets in a format the AI agent can analyze."""
    print(f"\n{'=' * 60}")
    print(f"TWITTER DATA FOR ${ticker}")
    print(f"Period: Last {DAYS_BACK} days | Quality tweets found: {len(tweets)}")
    print(f"{'=' * 60}\n")

    if not tweets:
        print("No quality tweets found. Either no buzz on this ticker, or the ticker is wrong.")
        return

    for i, tweet in enumerate(tweets, 1):
        verified_tag = "[VERIFIED] " if tweet['author_verified'] else ""
        print(f"--- Tweet #{i} ---")
        print(f"Author: {verified_tag}@{tweet['author_username']} ({tweet['author_name']}) | Followers: {tweet['author_followers']:,}")
        print(f"Stats: {tweet['likes']} likes | {tweet['retweets']} RT | {tweet['replies']} replies | {tweet['impressions']} impressions")
        print(f"Quality Score: {tweet['quality_score']}")
        print(f"Date: {tweet['created_at']}")
        print(f"Text:\n{tweet['text']}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python twitter_stock_analyzer.py <TICKER>")
        print("Example: python twitter_stock_analyzer.py SOFI")
        sys.exit(1)

    ticker = sys.argv[1].upper().replace('$', '')
    tweets = search_stock_tweets(ticker)
    print_results(ticker, tweets)
