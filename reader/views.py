# reader/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.dateparse import parse_datetime
import requests
import threading
from queue import Queue
from gtts import gTTS
from playsound import playsound
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from textblob import TextBlob
from .models import MonitoredPage, Post, Comment, Keyword

# --- CONFIGURATION ---
API_VERSION = "v19.0"

# --- GLOBAL STATE & BACKGROUND TASK QUEUE ---
comment_queue = Queue()
monitoring_thread = None
stop_thread_flag = False
thread_lock = threading.Lock()

# ------------------ HELPER & BACKGROUND FUNCTIONS ------------------

def format_fb_timestamp(timestamp_str):
    """Converts Facebook's UTC timestamp to Nepal Time (NPT) in a readable format."""
    if not timestamp_str: return ""
    try:
        utc_dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S%z')
        nepal_tz = ZoneInfo("Asia/Kathmandu")
        nepal_dt = utc_dt.astimezone(nepal_tz)
        return nepal_dt.strftime('%b %d, %Y at %I:%M %p')
    except (ValueError, TypeError):
        return timestamp_str

def speaker_thread_worker():
    """This function runs in a dedicated thread to speak comments from the queue one by one."""
    while True:
        text_to_speak = comment_queue.get()
        if text_to_speak is None: break
        print(f"   🎤 Now speaking: '{text_to_speak}'")
        try:
            filename = f"comment_{uuid.uuid4().hex}.mp3"
            tts = gTTS(text=text_to_speak, lang="en")
            tts.save(filename)
            playsound(filename)
            os.remove(filename)
        except Exception as e:
            print(f"❌ Speech Error: {e}")
        finally:
            comment_queue.task_done()

def speak_text(text_to_speak):
    """Adds a comment's text to the speaking queue."""
    print(f"✅ Queued for speaking: '{text_to_speak}'")
    comment_queue.put(text_to_speak)

def monitor_comments_thread(post_id, access_token):
    """The main background thread for fetching, analyzing, and saving comments."""
    processed_comment_ids = set()
    global stop_thread_flag
    poll_interval_seconds = 15
    print(f"🟢 Monitoring started for post {post_id}")
    
    try:
        post_object = Post.objects.get(post_id=post_id)
        alert_keywords = list(Keyword.objects.values_list('word', flat=True))
        print(f"   [Config] Monitoring with keywords: {alert_keywords if alert_keywords else 'None (all comments will be spoken)'}")
    except Post.DoesNotExist:
        print(f"❌ CRITICAL ERROR: Post {post_id} not found in the database. Stopping monitor.")
        return

    # Phase 1: Backfill all existing comments
    print("   [Phase 1] Reading all existing comments...")
    next_url = f"https://graph.facebook.com/{API_VERSION}/{post_id}/comments?access_token={access_token}&limit=100"
    while next_url and not stop_thread_flag:
        try:
            resp = requests.get(next_url, timeout=10).json()
            if "error" in resp: print(f"❌ FB ERROR: {resp['error']['message']}"); break
            for comment in reversed(resp.get("data", [])):
                comment_id = comment['id']
                message = comment.get('message', '').strip()
                if comment_id not in processed_comment_ids:
                    if message:
                        analysis = TextBlob(message)
                        sentiment_result = 'neutral'
                        if analysis.sentiment.polarity > 0.1: sentiment_result = 'positive'
                        elif analysis.sentiment.polarity < -0.1: sentiment_result = 'negative'
                        
                        if not alert_keywords or any(kw.lower() in message.lower() for kw in alert_keywords):
                            speak_text(message)

                        Comment.objects.get_or_create(
                            comment_id=comment_id,
                            defaults={
                                'post': post_object, 'message': message,
                                'created_time': parse_datetime(comment['created_time']),
                                'sentiment': sentiment_result
                            }
                        )
                    processed_comment_ids.add(comment['id'])
            next_url = resp.get("paging", {}).get("next")
        except Exception as e: print(f"❌ Error during backfill: {e}"); break

    # Phase 2: Live Monitoring for new comments
    print("   [Phase 2] Backfill complete. Now monitoring for new comments...")
    while not stop_thread_flag:
        try:
            url = f"https://graph.facebook.com/{API_VERSION}/{post_id}/comments?access_token={access_token}&limit=25"
            resp = requests.get(url, timeout=10).json()
            if "error" in resp: print(f"❌ FB ERROR: {resp['error']['message']}")
            else:
                for comment in reversed(resp.get("data", [])):
                    comment_id = comment['id']
                    message = comment.get('message', '').strip()
                    if comment_id not in processed_comment_ids:
                        print("   -> New comment found!")
                        if message:
                            analysis = TextBlob(message)
                            sentiment_result = 'neutral'
                            if analysis.sentiment.polarity > 0.1: sentiment_result = 'positive'
                            elif analysis.sentiment.polarity < -0.1: sentiment_result = 'negative'

                            if not alert_keywords or any(kw.lower() in message.lower() for kw in alert_keywords):
                                speak_text(message)

                            Comment.objects.get_or_create(
                                comment_id=comment_id,
                                defaults={
                                    'post': post_object, 'message': message,
                                    'created_time': parse_datetime(comment['created_time']),
                                    'sentiment': sentiment_result
                                }
                            )
                        processed_comment_ids.add(comment['id'])
        except Exception as e: print(f"❌ Error in live monitoring: {e}")
        time.sleep(poll_interval_seconds)
    print("🛑 Monitoring stopped.")

# Start the speaker thread once when the server starts
speaker_worker = threading.Thread(target=speaker_thread_worker, daemon=True)
speaker_worker.start()

# ------------------ DJANGO VIEWS (Web Page Logic) ------------------

def index(request):
    context = {
        'posts': request.session.get('last_fetched_posts'),
        'monitoring_post_id': request.session.get('monitoring_post_id'),
        'page_id': request.session.get('page_id'),
    }
    return render(request, 'reader/index.html', context)

def fetch_posts(request):
    if request.method == 'POST':
        page_id = request.POST.get("page_id", "").strip()
        access_token = request.POST.get("access_token", "").strip()

        if not page_id or not access_token:
            messages.error(request, "Page ID and Access Token are required.")
            return redirect('index')

        request.session['page_id'] = page_id
        request.session['access_token'] = access_token
        
        page_obj, created = MonitoredPage.objects.update_or_create(
            page_id=page_id, defaults={'access_token': access_token}
        )
        
        fields = "message,id,created_time,full_picture"
        url = f"https://graph.facebook.com/{API_VERSION}/{page_id}/posts?fields={fields}&limit=8&access_token={access_token}"
        
        try:
            resp = requests.get(url, timeout=10).json()
            if "error" in resp:
                messages.error(request, f"Facebook error: {resp['error']['message']}")
                request.session['last_fetched_posts'] = []
            else:
                posts_data = resp.get("data", [])
                for post_data in posts_data:
                    Post.objects.update_or_create(
                        post_id=post_data['id'],
                        defaults={
                            'page': page_obj, 'message': post_data.get('message', ''),
                            'created_time': parse_datetime(post_data['created_time'])
                        }
                    )
                    # Add formatted time for immediate display in the template
                    post_data['formatted_time'] = format_fb_timestamp(post_data.get('created_time'))
                
                request.session['last_fetched_posts'] = posts_data
                messages.success(request, f"Successfully fetched and saved {len(posts_data)} recent posts.")
        except Exception as e:
            messages.error(request, f"Connection error: {e}")
            request.session['last_fetched_posts'] = []
    
    return redirect('index')

def start_monitoring(request):
    global monitoring_thread, stop_thread_flag
    if request.method == 'POST':
        access_token = request.session.get("access_token")
        post_id = request.POST.get("post_id")
        
        if not access_token:
            messages.error(request, "Fetch posts first to provide credentials.")
            return redirect('index')

        with thread_lock:
            if monitoring_thread and monitoring_thread.is_alive():
                messages.warning(request, "Monitoring is already running. Stop it first.")
            else:
                stop_thread_flag = False
                request.session['monitoring_post_id'] = post_id
                monitoring_thread = threading.Thread(target=monitor_comments_thread, args=(post_id, access_token), daemon=True)
                monitoring_thread.start()
                messages.success(request, f"Started monitoring comments for post {post_id}.")
    return redirect('index')

def stop_monitoring(request):
    global stop_thread_flag
    if request.method == 'POST':
        with thread_lock:
            if monitoring_thread and monitoring_thread.is_alive():
                stop_thread_flag = True
                messages.info(request, "Stopping monitoring...")
            else:
                messages.warning(request, "No active monitoring to stop.")
            request.session['monitoring_post_id'] = None
    return redirect('index')

def comment_dashboard(request, post_id):
    post = get_object_or_404(Post, post_id=post_id)
    comments = Comment.objects.filter(post=post).order_by('-created_time')

    search_query = request.GET.get('search', '').strip()
    sentiment_filter = request.GET.get('sentiment', '')

    if search_query:
        comments = comments.filter(message__icontains=search_query)
    
    if sentiment_filter in ['positive', 'negative', 'neutral']:
        comments = comments.filter(sentiment=sentiment_filter)

    # Add formatted time to each comment for the template
    for comment in comments:
        comment.formatted_time = format_fb_timestamp(str(comment.created_time))
    
    post.formatted_time = format_fb_timestamp(str(post.created_time))

    context = {
        'post': post,
        'comments': comments,
        'comment_count': comments.count(),
        'search_query': search_query,
        'sentiment_filter': sentiment_filter,
    }
    return render(request, 'reader/comment_dashboard.html', context)

def manage_keywords(request):
    if request.method == 'POST':
        word_to_add = request.POST.get('word', '').strip().lower()
        word_to_delete = request.POST.get('delete_word', '')

        if word_to_add:
            if not Keyword.objects.filter(word=word_to_add).exists():
                Keyword.objects.create(word=word_to_add)
                messages.success(request, f"Keyword '{word_to_add}' added.")
            else:
                messages.warning(request, f"Keyword '{word_to_add}' already exists.")
        
        if word_to_delete:
            Keyword.objects.filter(id=word_to_delete).delete()
            messages.info(request, "Keyword deleted.")

        return redirect('manage_keywords')

    keywords = Keyword.objects.all().order_by('word')
    return render(request, 'reader/manage_keywords.html', {'keywords': keywords})