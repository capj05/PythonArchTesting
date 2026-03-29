"""Django models for testing architecture validation."""

from django.db import models


class TestModel(models.Model):
    """Test model for Django project."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "myapp"

    def __str__(self):
        return self.name


class RelatedModel(models.Model):
    """Related model for testing relationships."""

    test_model = models.ForeignKey(
        TestModel, on_delete=models.CASCADE, related_name="related_models"
    )
    value = models.IntegerField()
    data = models.JSONField(default=dict)

    class Meta:
        app_label = "myapp"

    def __str__(self):
        return f"{self.test_model.name} - {self.value}"
