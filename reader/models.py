# reader/models.py
from django.db import models

class MonitoredPage(models.Model):
    page_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    access_token = models.CharField(max_length=500) # In a real app, encrypt this!

    def __str__(self):
        return self.name or self.page_id

class Post(models.Model):
    page = models.ForeignKey(MonitoredPage, on_delete=models.CASCADE)
    post_id = models.CharField(max_length=100, unique=True)
    message = models.TextField(blank=True, null=True)
    created_time = models.DateTimeField()
    is_monitoring = models.BooleanField(default=False)

    def __str__(self):
        return self.post_id

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    comment_id = models.CharField(max_length=100, unique=True)
    message = models.TextField()
    created_time = models.DateTimeField()
    # Make sure this line is here and saved!
    sentiment = models.CharField(max_length=10, blank=True, null=True)

class Keyword(models.Model):
    """A model to store keywords that trigger audio alerts."""
    word = models.CharField(max_length=100, unique=True, help_text="The keyword to listen for (case-insensitive).")
    

    def __str__(self):
        return self.comment_id
