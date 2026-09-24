from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    email = models.EmailField(unique=True)
    sector = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=12, default='collaborator')
    rooms = models.BooleanField(default=True)
    vehicles = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)

class Resource(models.Model):
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    kind = models.CharField(max_length=12)
    active = models.BooleanField(default=True)
    opens = models.PositiveSmallIntegerField(default=360)
    closes = models.PositiveSmallIntegerField(default=1439)
    periods = models.JSONField(default=dict)

class Occupancy(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    start = models.DateTimeField()
    end = models.DateTimeField()
    kind = models.CharField(max_length=12, default='booking')
    mode = models.CharField(max_length=12, default='hours')
    title = models.CharField(max_length=180)
    destination = models.CharField(max_length=250, blank=True)
    driver = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True, max_length=2000)
    cancelled = models.BooleanField(default=False)
    request_key = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner','request_key'], name='unique_request'), models.CheckConstraint(condition=models.Q(end__gt=models.F('start')), name='positive_interval')]
        indexes = [models.Index(fields=['resource','start','end','cancelled'])]

class BookingEmail(models.Model):
    occupancy = models.OneToOneField(Occupancy, on_delete=models.PROTECT)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=200, blank=True)


class Invitation(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64, unique=True)
    purpose = models.CharField(max_length=12, default='invite')
    expires = models.DateTimeField()
    used = models.BooleanField(default=False)

class Audit(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=80)
    changes = models.JSONField(default=dict)
    reason = models.TextField(blank=True)

class Settings(models.Model):
    domains = models.JSONField(default=list)

class Attempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    since = models.DateTimeField()
