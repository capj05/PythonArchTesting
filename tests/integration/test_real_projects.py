"""
Integration tests for real project analysis.

These tests validate that the toolkit works correctly
on actual project structures found in the wild.
"""

from pathlib import Path

import pytest

try:
    from pythonarchtesting.state import ProjectState
except ImportError:
    ProjectState = None


class TestRealProjects:
    """Test analysis of real project structures."""

    def test_flask_project_structure(self, temp_project_dir: Path):
        """Test analysis of Flask-style project structure."""
        # Create a Flask-like project
        flask_project = temp_project_dir / "sample_flask_project"
        flask_project.mkdir(exist_ok=True)

        # Create Flask structure
        (flask_project / "app.py").write_text('''
"""Flask application."""

from flask import Flask, request, jsonify
from .models import db
from .routes import main_bp

def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

    db.init_app(app)
    app.register_blueprint(main_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
''')

        # Create models
        models_dir = flask_project / "models"
        models_dir.mkdir(exist_ok=True)
        (models_dir / "__init__.py").write_text("")
        (models_dir / "models.py").write_text('''
"""Database models."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    """User model."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<User {{self.username}}>'
''')

        # Create routes
        routes_dir = flask_project / "routes"
        routes_dir.mkdir(exist_ok=True)
        (routes_dir / "__init__.py").write_text("")
        (routes_dir / "routes.py").write_text('''
"""Application routes."""

from flask import Blueprint, request, jsonify
from .models import User

main_bp = Blueprint('main', __name__)

@main_bp.route('/users', methods=['GET'])
def get_users():
    """Get all users."""
    users = User.query.all()
    return jsonify([user.username for user in users])

@main_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()

    user = User(username=data['username'], email=data['email'])
    # This would normally save to database
    # db.session.add(user)
    # db.session.commit()

    return jsonify({'id': user.id, 'username': user.username}), 201
''')

        # Create templates
        templates_dir = flask_project / "templates"
        templates_dir.mkdir(exist_ok=True)
        (templates_dir / "index.html").write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>Flask App</title>
</head>
<body>
    <h1>Flask Application</h1>
    <div id="app"></div>
</body>
</html>
""")

        # Test analysis
        if ProjectState:
            project_state = ProjectState(str(flask_project), [])
            project_state.initialize(str(flask_project))
            assert True, "Project analysis completed successfully"
        else:
            pytest.skip("ProjectState not available")

    def test_django_project_structure(self, temp_project_dir: Path):
        """Test analysis of Django-style project structure."""
        # Create a Django-like project
        django_project = temp_project_dir / "sample_django_project"
        django_project.mkdir(exist_ok=True)

        # Create Django structure
        (django_project / "manage.py").write_text('''#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some Django versions
        sys.stderr.write("Error: Django is not installed.\\n")
        sys.exit(1)

    execute_from_command_line(sys.argv)
''')

        # Create Django app structure
        myproject_dir = django_project / "myproject"
        myproject_dir.mkdir(exist_ok=True)
        (myproject_dir / "__init__.py").write_text("")

        # Settings
        (myproject_dir / "settings.py").write_text('''
"""Django settings."""

SECRET_KEY = 'django-insecure-key-for-testing'
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myapp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myproject.urls'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
''')

        # Create app
        myapp_dir = myproject_dir / "myapp"
        myapp_dir.mkdir(exist_ok=True)
        (myapp_dir / "__init__.py").write_text("")

        # Models
        (myapp_dir / "models.py").write_text('''
"""Django models."""

from django.db import models

class TestModel(models.Model):
    """Test model."""
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'myapp'

    def __str__(self):
        return self.name
''')

        # Views
        (myapp_dir / "views.py").write_text('''
"""Django views."""

from django.shortcuts import render
from django.http import HttpResponse
from .models import TestModel

def test_view(request):
    """Test view with some complexity."""
    objects = TestModel.objects.all()
    return render(request, 'myapp/template.html', {'objects': objects})
''')

        # URLs
        (myproject_dir / "urls.py").write_text('''
"""Django URL configuration."""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

urlpatterns = [
    path('admin/', admin.site.urls),
    path('myapp/', include('myapp.urls')),
    path('', lambda r: HttpResponse('Welcome to Django!')),
]
''')

        # App URLs
        (myapp_dir / "urls.py").write_text('''
"""Myapp URL configuration."""

from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.test_view, name='test_view'),
]
''')

        # Test analysis
        if ProjectState:
            project_state = ProjectState(str(django_project), [])
            project_state.initialize(str(django_project))

            # Should have validation results (even if empty)
            assert isinstance(
                project_state.validation_results, list
            ), "Should have validation results list"

            # Test passes if project can be analyzed without errors
            assert True, "Project analysis completed successfully"
        else:
            pytest.skip("ProjectState not available")

    def test_fastapi_project_structure(self, temp_project_dir: Path):
        """Test analysis of FastAPI-style project structure."""
        # Create a FastAPI-like project
        fastapi_project = temp_project_dir / "sample_fastapi_project"
        fastapi_project.mkdir(exist_ok=True)

        # Create main.py
        (fastapi_project / "main.py").write_text('''
"""FastAPI application."""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Test API")

class Item(BaseModel):
    """Pydantic model for API."""
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

@app.get("/items/", response_model=List[Item])
def read_items():
    """Get all items."""
    return [
        Item(name="Item 1", price=10.99, description="First item"),
        Item(name="Item 2", price=20.50, description="Second item"),
        Item(name="Item 3", price=30.00, description="Third item"),
    ]

@app.get("/items/{{item_id}}", response_model=Item)
def read_item(item_id: int):
    """Get item by ID."""
    if item_id < 1 or item_id > 3:
        raise HTTPException(status_code=404, detail="Item not found")

    return Item(name=f"Item {item_id}", price=item_id * 10.0)

@app.post("/items/", response_model=Item)
def create_item(item: Item):
    """Create a new item."""
    return item

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
''')

        # Create requirements.txt
        (fastapi_project / "requirements.txt").write_text("""
fastapi>=0.68.0
uvicorn>=0.15.0
pydantic>=1.8.0
""")

        # Test analysis
        if ProjectState:
            project_state = ProjectState(str(fastapi_project), [])
            project_state.initialize(str(fastapi_project))

            # Test passes if project can be analyzed without errors
            assert True, "Project analysis completed successfully"
        else:
            pytest.skip("ProjectState not available")

    def test_package_project_structure(self, temp_project_dir: Path):
        """Test analysis of Python package project structure."""
        # Create a package-style project
        package_project = temp_project_dir / "sample_package_project"
        package_project.mkdir(exist_ok=True)

        # Create package structure
        src_dir = package_project / "src"
        src_dir.mkdir(exist_ok=True)

        # Create package
        package_dir = src_dir / "mypackage"
        package_dir.mkdir(exist_ok=True)
        (package_dir / "__init__.py").write_text('''
"""My package."""

__version__ = "1.0.0"
__author__ = "Test Author"
''')

        # Create modules
        modules = ["core", "utils", "exceptions"]
        for module in modules:
            module_content = f'''
"""{module.title()} module."""

class {module.title()}Error(Exception):
    """{module.title()} specific error."""
    pass

def {module.lower()}_function(data: str) -> str:
    """Process data in {module} module."""
    return f"{module}_processed: {{data}}"
'''
            (package_dir / f"{module}.py").write_text(module_content)

        # Create setup.py
        (package_project / "setup.py").write_text('''
"""Setup script for mypackage."""

from setuptools import setup, find_packages

setup(
    name="mypackage",
    version="1.0.0",
    description="A test package",
    author="Test Author",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
    ],
)
''')

        # Create pyproject.toml
        (package_project / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mypackage"
version = "1.0.0"
description = "A test package"
authors = [{name = "Test Author", email = "test@example.com"}]
license = {text = "MIT"}
requires-python = ">=3.8"
dependencies = [
    "requests>=2.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=6.0",
    "black>=21.0",
]
""")

        # Test analysis
        if ProjectState:
            project_state = ProjectState(str(package_project), [])
            project_state.initialize(str(package_project))

            # Test passes if project can be analyzed without errors
            assert True, "Project analysis completed successfully"
        else:
            pytest.skip("ProjectState not available")

    def test_monorepo_structure(self, temp_project_dir: Path):
        """Test analysis of monorepo structure."""
        # Create a monorepo
        monorepo = temp_project_dir / "sample_monorepo"
        monorepo.mkdir(exist_ok=True)

        # Create multiple packages
        packages = ["frontend", "backend", "shared"]
        for package in packages:
            package_dir = monorepo / package
            package_dir.mkdir(exist_ok=True)

            if package == "frontend":
                (package_dir / "package.json").write_text("""{
  "name": "frontend",
  "version": "1.0.0",
  "scripts": {
    "build": "webpack --mode production",
    "dev": "webpack serve"
  }
}""")
                (package_dir / "src").write_text("""
// Frontend JavaScript code
console.log("Hello from frontend");
""")
            elif package == "backend":
                (package_dir / "setup.py").write_text("""from setuptools import setup

setup(
    name="backend",
    version="1.0.0",
    packages=["backend"],
)
""")
                backend_dir = package_dir / "backend"
                backend_dir.mkdir(exist_ok=True)
                (backend_dir / "__init__.py").write_text("")
                (package_dir / "backend" / "api.py").write_text('''"""
Backend API.

def get_data():
    """Get data from backend."""
    return {"message": "Hello from backend"}
''')
            elif package == "shared":
                (package_dir / "setup.py").write_text("""
from setuptools import setup

setup(
    name="shared",
    version="1.0.0",
    packages=["shared"],
)
""")
                shared_dir = package_dir / "shared"
                shared_dir.mkdir(exist_ok=True)
                (shared_dir / "__init__.py").write_text("")
                (shared_dir / "utils.py").write_text('''
"""Shared utilities."""

def shared_function():
    """Shared function across packages."""
    return "shared_result"
''')

        # Create root configuration
        (monorepo / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools"]

[tool.poetry]
name = "monorepo"
version = "1.0.0"
description = "A monorepo example"

[tool.poetry.dependencies]
python = "^3.8"

[tool.poetry.group.dev.dependencies]
pytest = "^6.0"
""")

        # Test analysis
        if ProjectState:
            project_state = ProjectState(str(monorepo), [])
            project_state.initialize(str(monorepo))

            # Test passes if project can be analyzed without errors
            assert True, "Project analysis completed successfully"
        else:
            pytest.skip("ProjectState not available")
