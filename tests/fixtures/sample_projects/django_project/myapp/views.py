"""Django views for testing architecture validation."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import TestModel


def test_view(request):
    """Test view with some complexity."""
    objects = TestModel.objects.all()
    return render(request, "myapp/test_template.html", {"objects": objects})


@require_http_methods(["GET", "POST"])
def api_view(request):
    """API view for testing."""
    if request.method == "GET":
        objects = TestModel.objects.filter(is_active=True)
        data = [
            {"id": obj.id, "name": obj.name, "description": obj.description}
            for obj in objects
        ]
        return JsonResponse({"results": data})
    else:
        return JsonResponse({"status": "created"}, status=201)


def complex_view(request):
    """Complex view with nested logic."""
    if request.method == "GET":
        param = request.GET.get("param", "")

        if param == "all":
            objects = TestModel.objects.all()
        elif param == "active":
            objects = TestModel.objects.filter(is_active=True)
        elif param == "inactive":
            objects = TestModel.objects.filter(is_active=False)
        else:
            objects = TestModel.objects.none()

        # Complex processing
        result = []
        for obj in objects:
            related_count = obj.related_models.count()
            result.append(
                {
                    "id": obj.id,
                    "name": obj.name,
                    "related_count": related_count,
                    "has_description": bool(obj.description),
                    "complexity_score": (
                        len(obj.description) if obj.description else 0 + related_count
                    ),
                }
            )

        # Sort by complexity
        result.sort(key=lambda x: x["complexity_score"], reverse=True)

        return JsonResponse({"results": result})

    return JsonResponse({"error": "Method not allowed"}, status=405)
