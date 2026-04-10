from sqlalchemy import func
from sqlalchemy.orm import Query

from Delivery_app_BK.models import OrderCase
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_case_states import OrderCaseState

def order_cases_stats(query: Query, ctx: ServiceContext):
    base_query = query.order_by(None).limit(None).offset(None)

    state_counts = (
        base_query
        .with_entities(
            OrderCase.state,
            func.count(OrderCase.id)
        )
        .group_by(OrderCase.state)
        .all()
    )


    state_map ={
        state:count
        for state,count in state_counts
        if state is not None
    }

    total_cases = sum(state_map.values())

  


    return {
        "order_cases": {
            "total": total_cases
        },
        "open_cases":{
            "total":state_map.get(OrderCaseState.OPEN,0)            
        },
        "resolving_cases":{
            "total":state_map.get(OrderCaseState.RESOLVING,0)      
        }
    }
