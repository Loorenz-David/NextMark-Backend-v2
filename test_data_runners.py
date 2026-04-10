
from Delivery_app_BK import create_app
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.test_data.cleanup import clear_generated_test_data

app = create_app()
with app.app_context():
    ctx = ServiceContext(
        incoming_data={"client_id_prefix": "td:beyo-import"},
        identity={"team_id": 1, "active_team_id": 1, "user_id": 1},
    )
    print(clear_generated_test_data(ctx))


"""

.venv/bin/python beyo-data-transfer/importer.py --team-id 1 --driver-id 1

"""