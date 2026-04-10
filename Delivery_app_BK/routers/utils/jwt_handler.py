from flask_jwt_extended import JWTManager

from Delivery_app_BK.errors import PermissionDenied, ValidationFailed
from Delivery_app_BK.routers.http.response import Response
from flask import request

jwt = JWTManager()

@jwt.unauthorized_loader
def missing_token_callback(error):
    response = Response()
    return response.build_unsuccessful_response(
        PermissionDenied("Missing Authorization Header")
    )

@jwt.invalid_token_loader
def invalid_token_callback(error):
    response = Response()
  
    return response.build_unsuccessful_response(
        ValidationFailed("Invalid token")
    )

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    response = Response()
    return response.build_unsuccessful_response(
        PermissionDenied("Token has expired")
    )
