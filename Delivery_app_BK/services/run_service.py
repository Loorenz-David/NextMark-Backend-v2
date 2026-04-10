from typing import Callable, Any, TypeVar
from Delivery_app_BK.errors import DomainError
from .outcome import StatusOutcome
from .context import ServiceContext
import logging


logger = logging.getLogger(__name__)

T = TypeVar("T")

def run_service( service_fn:Callable[ [ServiceContext], T ], ctx:ServiceContext ) -> StatusOutcome:

    try:
        data = service_fn( ctx )
        
        return StatusOutcome( data = data )
    
    except DomainError as e:
        return StatusOutcome( error = e )
    except Exception as e:
        logger.exception(
            "Unexpected exception in service %s | identity=%s | data=%s",
            service_fn.__name__,
            ctx.identity,
            ctx.incoming_data
        )
        return StatusOutcome( error= DomainError("Unexpected internal error"))
    
    