"""Flask application for testing architecture validation."""

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Sample data storage (in production, this would be a database)
users = []
posts = []


@app.route("/")
def index():
    """Home page route."""
    return render_template("index.html", users=users, posts=posts)


@app.route("/users", methods=["GET", "POST"])
def users_endpoint():
    """Users endpoint with CRUD operations."""
    if request.method == "GET":
        return jsonify({"users": users})
    else:
        data = request.get_json()
        user = {
            "id": len(users) + 1,
            "name": data.get("name"),
            "email": data.get("email"),
            "active": data.get("active", True),
        }
        users.append(user)
        return jsonify(user), 201


@app.route("/users/<int:user_id>", methods=["GET", "PUT", "DELETE"])
def user_detail(user_id: int):
    """User detail endpoint."""
    user = next((u for u in users if u["id"] == user_id), None)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == "GET":
        return jsonify(user)
    elif request.method == "PUT":
        data = request.get_json()
        user.update(data)
        return jsonify(user)
    else:  # DELETE
        users.remove(user)
        return jsonify({"message": "User deleted"})


@app.route("/posts", methods=["GET", "POST"])
def posts_endpoint():
    """Posts endpoint with validation logic."""
    if request.method == "GET":
        # Complex filtering logic
        author_id = request.args.get("author_id")
        active_only = request.args.get("active_only", "false").lower() == "true"

        filtered_posts = posts

        if author_id:
            try:
                author_id = int(author_id)
                filtered_posts = [
                    p for p in filtered_posts if p["author_id"] == author_id
                ]
            except ValueError:
                return jsonify({"error": "Invalid author_id"}), 400

        if active_only:
            filtered_posts = [p for p in filtered_posts if p.get("active", True)]

        # Sort and paginate
        filtered_posts.sort(key=lambda x: x["created_at"], reverse=True)

        return jsonify({"posts": filtered_posts})
    else:
        data = request.get_json()

        # Validation logic
        required_fields = ["title", "content", "author_id"]
        if not all(field in data for field in required_fields):
            missing = [field for field in required_fields if field not in data]
            return jsonify({"error": f"Missing required fields: {missing}"}), 400

        try:
            author_id = int(data["author_id"])
            author = next((u for u in users if u["id"] == author_id), None)
            if not author:
                return jsonify({"error": "Author not found"}), 400
        except ValueError:
            return jsonify({"error": "Invalid author_id"}), 400

        post = {
            "id": len(posts) + 1,
            "title": data["title"],
            "content": data["content"],
            "author_id": author_id,
            "author_name": author["name"],
            "created_at": "2023-01-01T00:00:00Z",  # In production, use actual timestamp
            "active": True,
            "tags": data.get("tags", []),
        }

        posts.append(post)
        return jsonify(post), 201


@app.route("/search")
def search_endpoint():
    """Search endpoint with complex query processing."""
    query = request.args.get("q", "").strip()
    search_type = request.args.get("type", "all")

    if not query:
        return jsonify({"error": "Query parameter required"}), 400

    query_lower = query.lower()
    results = []

    if search_type in ["all", "users"]:
        # Search users
        user_results = [
            user
            for user in users
            if query_lower in user["name"].lower()
            or query_lower in user["email"].lower()
        ]
        results.extend([{"type": "user", "data": user} for user in user_results])

    if search_type in ["all", "posts"]:
        # Search posts
        post_results = [
            post
            for post in posts
            if (
                query_lower in post["title"].lower()
                or query_lower in post["content"].lower()
                or any(query_lower in tag.lower() for tag in post.get("tags", []))
            )
        ]
        results.extend([{"type": "post", "data": post} for post in post_results])

    # Sort by relevance (simple implementation)
    results.sort(
        key=lambda x: (
            1 if query_lower in x["data"]["title"].lower() else 0,
            len(x["data"].get("tags", [])),
            len(x["data"].get("content", "")),
        ),
        reverse=True,
    )

    return jsonify(
        {"query": query, "type": search_type, "count": len(results), "results": results}
    )


@app.errorhandler(404)
def not_found(_error):
    """Custom 404 handler."""
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(500)
def internal_error(_error):
    """Custom 500 handler."""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True)
