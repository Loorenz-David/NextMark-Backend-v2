from Delivery_app_BK.errors import DomainError


class StatusOutcome():

    def __init__( self, data=None, error=None ):
        self.data = data
        self.error:DomainError = error
    
    @property
    def success(self):
        return self.error is None