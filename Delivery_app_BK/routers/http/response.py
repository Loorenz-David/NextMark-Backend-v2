from Delivery_app_BK.errors import DomainError
from Delivery_app_BK.errors import NotFound 
from Delivery_app_BK.errors import PermissionDenied 
from Delivery_app_BK.errors import ValidationFailed 

from flask import jsonify



class Response():

    """
    Http statuses are the common ones but added +10
    as the front end ( CloudFront ) intercepts 400 - 405 to render the one page app
    """
    status_map = {
        NotFound : 414,
        PermissionDenied : 413,
        ValidationFailed : 410,
        DomainError: 510,
    }
    
    def __init__( self, error=None, payload=None ): 
        self.error = error
        self.payload = payload

    def build_successful_response(self, payload=None, warnings=[], status = 200 ):

        set_payload = payload or self.payload
       
        return jsonify({
            "data": set_payload,
            "warnings": warnings,
        }), status
    
    def build_unsuccessful_response( self, error=None ):

        err:DomainError = error or self.error

        status = self.status_map.get( type(err), self.status_map[DomainError] )

        return jsonify({
            "error": err.message,
            "code": err.code,
        }), status
    


"""
later development: 
outcome = run_service(find_users, ctx)

response = Response()

if not outcome.success:
    return response.build_unsuccessful_response(outcome.error)

return response.build_successful_response(outcome.data, warnings=ctx.warnings)


and the compression and uncompression happens on an app listener
place at the app factory!!
"""