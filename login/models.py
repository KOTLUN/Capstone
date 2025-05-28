from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Remove UserProfile model and its signals since we're using force_password_change
# directly in Teachers and Student models
