from .shopify import shopify_webhook_bp


def register_webhook_blueprints(app):
    app.register_blueprint(shopify_webhook_bp, url_prefix="/webhooks/shopify")
