import streamlit as st
import requests
import os
import pandas as pd
from datetime import datetime

# API Configurations
INSTAGRAM_API_HOST = st.secrets.get("INSTAGRAM_API_HOST", "instagram-scraper-api2.p.rapidapi.com")
TWITTER_API_HOST = st.secrets.get("TWITTER_API_HOST", "twitter241.p.rapidapi.com")
RAPIDAPI_KEY = st.secrets.get("RAPIDAPI_KEY")

# [Previous Instagram Functions remain the same]
def fetch_instagram_data(username):
    """Fetch Instagram data for a given username"""
    headers = {
        "x-rapidapi-host": INSTAGRAM_API_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    profile_data = None
    posts_data = None
    followers_data = None

    try:
        # Fetch profile info with retry for private accounts
        profile_url = f"https://{INSTAGRAM_API_HOST}/v1/info?username_or_id_or_url={username}"
        profile_response = requests.get(profile_url, headers=headers, timeout=10)
        
        if profile_response.status_code != 200:
            st.error(f"Failed to fetch profile. Status code: {profile_response.status_code}")
            return None, None, None

        profile_data = profile_response.json().get('data', {})
        
        if not profile_data:
            st.error("No profile data found")
            return None, None, None

        # If account is private, try alternate endpoint
        if profile_data.get('is_private', True):
            profile_url = f"https://{INSTAGRAM_API_HOST}/v1.2/info?username_or_id_or_url={username}"
            profile_response = requests.get(profile_url, headers=headers, timeout=10)
            if profile_response.status_code == 200:
                profile_data = profile_response.json().get('data', {})
            return profile_data, None, None

        # Fetch posts
        posts_url = f"https://{INSTAGRAM_API_HOST}/v1.2/posts?username_or_id_or_url={username}"
        posts_response = requests.get(posts_url, headers=headers, timeout=10)
        
        if posts_response.status_code == 200:
            posts_data = posts_response.json().get('data', {})
        else:
            st.warning(f"Failed to fetch posts. Status code: {posts_response.status_code}")
            posts_data = None

        # Fetch followers (only if account is public)
        followers_url = f"https://{INSTAGRAM_API_HOST}/v1/following?username_or_id_or_url={username}"
        followers_response = requests.get(followers_url, headers=headers, timeout=10)
        
        if followers_response.status_code == 200:
            followers_data = followers_response.json().get('data', {})
        else:
            followers_data = None

        return profile_data, posts_data, followers_data

    except Exception as e:
        st.error(f"Error occurred: {e}")
        return None, None, None

def download_instagram_media(profile_data, posts_data):
    """Download Instagram profile picture and posts"""
    profile_pic_path = None
    downloaded_posts = []
    post_data = []

    # Download profile picture
    try:
        profile_pic_url = profile_data.get('hd_profile_pic_url_info', {}).get('url')
        if profile_pic_url:
            os.makedirs("downloads/instagram/profile", exist_ok=True)
            response = requests.get(profile_pic_url, timeout=10)
            if response.status_code == 200:
                profile_pic_path = "downloads/instagram/profile/profile_pic.jpg"
                with open(profile_pic_path, 'wb') as file:
                    file.write(response.content)
    except Exception as e:
        st.warning(f"Could not download profile picture: {e}")

    # Download posts
    if posts_data and isinstance(posts_data, dict):
        try:
            os.makedirs("downloads/instagram/posts", exist_ok=True)
            items = posts_data.get('items', [])
            
            if not items:
                st.warning("No posts found for this account.")
                return profile_pic_path, downloaded_posts, post_data

            for index, item in enumerate(items[:10]):  # Limit to 10 posts
                try:
                    # Get image versions with fallback options
                    image_versions = (
                        (item.get('image_versions2', {}) or {}).get('candidates', []) or
                        (item.get('carousel_media', [{}])[0].get('image_versions2', {}) or {}).get('candidates', []) or
                        item.get('image_versions', {}).get('items', [])
                    )

                    if image_versions and len(image_versions) > 0:
                        image_url = image_versions[0].get('url')
                        if image_url:
                            response = requests.get(image_url, timeout=10)
                            if response.status_code == 200:
                                filename = f"downloads/instagram/posts/post_{index}.jpg"
                                with open(filename, 'wb') as file:
                                    file.write(response.content)
                                downloaded_posts.append(filename)

                                # Get caption with safe navigation
                                caption = item.get('caption', {})
                                caption_text = caption.get('text', '') if isinstance(caption, dict) else ''

                                # Collect post data
                                post_data.append({
                                    'caption': caption_text,
                                    'likes': item.get('like_count', 0),
                                    'comments': item.get('comment_count', 0),
                                    'timestamp': item.get('taken_at', ''),
                                    'image_path': filename,
                                    'location': (item.get('location', {}) or {}).get('name', ''),
                                    'type': item.get('media_type', 1)
                                })
                except Exception as post_error:
                    st.warning(f"Could not process post {index + 1}: {post_error}")
                    continue

        except Exception as e:
            st.warning(f"Could not download posts: {e}")
    else:
        st.warning("No posts data available or account might be private.")

    return profile_pic_path, downloaded_posts, post_data

# Twitter Functions
def get_twitter_user_data(username):
    """Fetch Twitter user data"""
    url = f"https://{TWITTER_API_HOST}/user?username={username}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": TWITTER_API_HOST,
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data["result"]["data"]["user"]["result"]
        return None
    except Exception as e:
        st.error(f"Error fetching Twitter data: {str(e)}")
        return None

def get_user_tweets(user_id, count=20):
    """Fetch user tweets"""
    url = f"https://{TWITTER_API_HOST}/user-tweets"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": TWITTER_API_HOST
    }
    params = {"user": user_id, "count": count}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"Failed to fetch tweets. Status code: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error fetching tweets: {str(e)}")
        return None

def parse_tweet(tweet_entry):
    """Extract tweet details"""
    try:
        content = tweet_entry.get('content', {})
        tweet_results = content.get('itemContent', {}).get('tweet_results', {}).get('result', {})

        if not tweet_results:
            return None
        
        legacy = tweet_results.get('legacy', {})
        if not legacy:
            return None

        return {
            'text': legacy.get('full_text', ''),
            'created_at': legacy.get('created_at', ''),
            'retweet_count': legacy.get('retweet_count', 0),
            'favorite_count': legacy.get('favorite_count', 0),
            'reply_count': legacy.get('reply_count', 0),
            'quote_count': legacy.get('quote_count', 0),
            'media': legacy.get('extended_entities', {}).get('media', [])
        }
    except Exception as e:
        st.error(f"Error parsing tweet: {str(e)}")
        return None

def display_tweet(tweet, is_pinned=False):
    """Display tweet with formatting"""
    with st.container():
        if is_pinned:
            st.markdown("📌 **Pinned Tweet**")
        st.markdown("---")
        st.markdown(f"**{tweet['text']}**")
        st.markdown(f"🔄 {tweet['retweet_count']} | ❤️ {tweet['favorite_count']} | 💬 {tweet['reply_count']} | 🔁 {tweet['quote_count']}")
        st.markdown(f"*Posted on: {tweet['created_at']}*")

        if tweet['media']:
            cols = st.columns(min(len(tweet['media']), 2))
            for idx, media in enumerate(tweet['media']):
                if media.get('type') == 'photo':
                    with cols[idx % 2]:
                        st.image(media.get('media_url_https', ''), width=250)

def main():
    # Page configuration
    st.set_page_config(
        page_title="Social Media Profile Viewer",
        layout="wide"
    )

    # Main title
    st.title("Social Media Profile Viewer")
    st.markdown("Explore Instagram and Twitter profiles in one place")
    st.markdown("---")

    # Create tabs for Instagram and Twitter
    tab1, tab2 = st.tabs(["📸 Instagram", "🐦 Twitter"])

    # Instagram Tab
    with tab1:
        st.header("Instagram Profile Viewer")
        insta_username = st.text_input("Enter Instagram Username", key="insta_input")
        
        if st.button("Fetch Instagram Profile", key="insta_button"):
            if insta_username:
                with st.spinner('Fetching Instagram data...'):
                    profile_data, posts_data, followers_data = fetch_instagram_data(insta_username)
                
                if profile_data:
                    profile_pic_path, downloaded_posts, post_data = download_instagram_media(profile_data, posts_data)
                    
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        if profile_pic_path:
                            st.image(profile_pic_path, width=150, caption=f"{profile_data.get('full_name')}'s Profile Picture")
                    
                    with col2:
                        st.header(profile_data.get('full_name'))
                        st.markdown(f"**Bio:** {profile_data.get('biography')}")
                        st.markdown(f"**Posts:** {profile_data.get('media_count')} | **Followers:** {profile_data.get('follower_count')} | **Following:** {profile_data.get('following_count')}")
                        st.markdown(f"**Account Type:** {profile_data.get('account_type')}")
                        
                        creation_timestamp = profile_data.get('created_time', '')
                        if creation_timestamp:
                            created_date = datetime.fromtimestamp(int(creation_timestamp)).strftime('%Y-%m-%d')
                            st.markdown(f"**Account Created:** {created_date}")
                        
                        if profile_data.get('external_url'):
                            st.markdown(f"**Website:** {profile_data.get('external_url')}")
                    
                    if post_data:
                        st.header("Recent Posts")
                        for post in post_data:
                            with st.container():
                                st.markdown("---")
                                cols = st.columns([1, 2])
                                with cols[0]:
                                    st.image(post['image_path'], width=300)
                                with cols[1]:
                                    if post['caption']:
                                        st.markdown(f"**Caption:** {post['caption']}")
                                    st.markdown(f"❤️ {post['likes']} likes | 💬 {post['comments']} comments")
                                    if post['location']:
                                        st.markdown(f"📍 {post['location']}")
                                    timestamp = datetime.fromtimestamp(post['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                                    st.markdown(f"*Posted on: {timestamp}*")
                                    media_type = "Photo 📷" if post['type'] == 1 else "Video 🎥" if post['type'] == 2 else "Carousel 📑"
                                    st.markdown(f"*Type: {media_type}*")
                    
                    if followers_data:
                        st.header("Followers")
                        followers_df = pd.DataFrame([
                            {
                                "Full Name": follower.get('full_name', 'N/A'),
                                "Username": follower.get('username', 'N/A'),
                                "Private Account": follower.get('is_private', 'N/A')
                            } for follower in followers_data.get('items', [])
                        ])
                        st.dataframe(followers_df)

    # Twitter Tab
    with tab2:
        st.header("Twitter Profile Viewer")
        twitter_username = st.text_input("Enter Twitter Username", key="twitter_input")
        
        if st.button("Fetch Twitter Profile", key="twitter_button"):
            if twitter_username:
                with st.spinner('Fetching Twitter data...'):
                    user_data = get_twitter_user_data(twitter_username)
                    
                    if user_data:
                        legacy_data = user_data.get('legacy', {})
                        
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            profile_image = legacy_data.get("profile_image_url_https", "").replace("_normal", "")
                            st.image(profile_image, width=150, caption=f"{legacy_data.get('name')}'s Profile Picture")
                        
                        with col2:
                            st.header(legacy_data.get('name'))
                            st.markdown(f"**Description:** {legacy_data.get('description')}")
                            st.markdown(f"**Followers:** {legacy_data.get('followers_count')} | **Following:** {legacy_data.get('friends_count')} | **Tweets:** {legacy_data.get('statuses_count')}")
                            st.markdown(f"**Location:** {legacy_data.get('location', 'Not specified')}")
                            st.markdown(f"**Joined:** {legacy_data.get('created_at')}")
                        
                        profile_banner = legacy_data.get("profile_banner_url")
                        if profile_banner:
                            st.image(profile_banner, width=600, caption="Profile Banner")
                        
                        st.header("Recent Tweets")
                        tweets_data = get_user_tweets(user_data.get('rest_id'))
                        
                        if tweets_data:
                            timeline_entries = tweets_data.get('result', {}).get('timeline', {}).get('instructions', [])
                            
                            for instruction in timeline_entries:
                                if instruction.get('type') == 'TimelinePinEntry':
                                    tweet = parse_tweet(instruction.get('entry', {}))
                                    if tweet:
                                        display_tweet(tweet, is_pinned=True)
                                
                                elif instruction.get('type') == 'TimelineAddEntries':
                                    for entry in instruction.get('entries', []):
                                        tweet = parse_tweet(entry)
                                        if tweet:
                                            display_tweet(tweet)

if __name__ == "__main__":
    main()
