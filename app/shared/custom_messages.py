class CustomMessages:
    healthy_service = "Service is healthy"
    degraded_service = "Service is degraded — a dependency is unreachable"

    # Generic
    validation_failed = "Request validation failed"
    internal_server_error = "Something went wrong. Please try again later."
    not_found = "Resource not found"

    # Auth
    login_success = "Login successful"
    invalid_credentials = "Invalid username or password"
    admin_fetched = "Admin fetched successfully"
    auth_header_missing = "Authorization header missing"
    token_expired = "Session expired. Please sign in again."
    token_invalid = "Session is invalid. Please sign in again."
    admin_not_configured = "Admin login is not configured on the server"
    too_many_attempts = "Too many failed attempts. Try again in 15 minutes."

    # Products
    products_fetched = "Products retrieved successfully"
    product_fetched = "Product retrieved successfully"
    categories_fetched = "Categories retrieved successfully"
    product_stats_fetched = "Product stats retrieved successfully"
    product_created = "Product created successfully"
    product_updated = "Product updated successfully"
    product_deleted = "Product deleted successfully"
    product_not_found = "Product does not exist"
    invalid_product_id = "Product id is not valid"
    nothing_to_update = "Provide at least one field (or a new image) to update"

    # Images
    image_too_large = "Image is too large"
    image_invalid = "File is not a valid image (allowed: JPEG, PNG, WEBP, GIF)"
    image_save_failed = "Failed to save the image"
