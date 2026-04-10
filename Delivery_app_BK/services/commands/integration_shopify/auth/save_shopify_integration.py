from datetime import datetime, timezone

from Delivery_app_BK.models import db, ShopifyIntegration, Team,User


from ....context import ServiceContext
from ...utils import build_create_result
from ...base.create_instance import create_instance
from ....queries.integration_shopify import get_integration

def save_shopify_integration( ctx:ServiceContext ):
    relationship_map = {
        "team_id":Team,
        "user_id":User
    }
    ctx.set_relationship_map(relationship_map)

    shop = ctx.incoming_data.get("shop")


    integration = get_integration(ctx, shop)


    if integration: 
        integration.access_token = ctx.incoming_data.get("access_token")
        integration.scopes = ctx.incoming_data.get( "scopes" )
        integration.connected_at = datetime.now(timezone.utc)
        result = integration
    else:
        
        instance = create_instance(
            ctx = ctx,
            Model = ShopifyIntegration,
            fields = ctx.incoming_data
        )

        db.session.add(instance)
        db.session.flush()
        result = build_create_result(ctx, [instance] )

    db.session.commit()

    return result