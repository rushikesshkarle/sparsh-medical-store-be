class CustomMessages:
    healthy_service = "Service is healthy"
    degraded_service = "Service is degraded — a dependency is unreachable"

    # Generic
    validation_failed = "Request validation failed"
    internal_server_error = "Something went wrong. Please try again later."
    not_found = "Resource not found"

    # Auth
    login_success = "Login successful"
    user_fetched = "User fetched successfully"
    auth_header_missing = "Authorization header missing"
    token_expired = "Access token has expired"
    token_invalid = "Access token is invalid"
    user_not_found = "User account no longer exists"
    user_disabled = "User account is disabled"
    admin_required = "Admin access required"

    # Google sign-in
    oauth_not_configured = "Google sign-in is not configured on the server"
    google_code_exchange_failed = "Google sign-in failed. Please try again."
    invalid_google_token = "Google sign-in token is invalid or expired"
    unexpected_token_issuer = "Google sign-in token has an unexpected issuer"
    email_not_verified = "Your Google email address is not verified"
    google_payload_missing = "Google sign-in did not return an email address"

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

    # Cart
    cart_fetched = "Cart retrieved successfully"
    cart_saved = "Cart saved successfully"

    # Images
    image_too_large = "Image is too large"
    image_invalid = "File is not a valid image (allowed: JPEG, PNG, WEBP, GIF)"
    image_save_failed = "Failed to save the image"
