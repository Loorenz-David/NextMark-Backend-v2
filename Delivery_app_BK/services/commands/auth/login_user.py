from Delivery_app_BK.models import db, User
from Delivery_app_BK.errors import ValidationFailed

from ...context import ServiceContext
from ...requests.auth.login import parse_login_request
from .token_utils import build_user_tokens



def login_user_service( ctx:ServiceContext ):

    target_user = ctx.incoming_data
    if not target_user:
        raise ValidationFailed("Missing username and password.")

    login_request = parse_login_request(target_user)
    user_query = db.session.query( User )
    user:User = user_query.filter( User.email == login_request.email ).first()

    if not user:
        raise ValidationFailed( "Incorrect login information." ) 
    
    if not user.check_password( login_request.password ):
        raise ValidationFailed( "Incorrect login information." ) 
    


    tokens = build_user_tokens(
        user,
        app_scope=login_request.app_scope,
        time_zone=login_request.time_zone,
    )
    db.session.commit()
    return tokens
