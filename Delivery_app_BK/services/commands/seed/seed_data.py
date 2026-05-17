from ..utils.client_id_generator import generate_client_id


def build_seed_payloads():
    base_roles = [
        {
            "id": 1,
            "role_name": "admin",
            "description": "System administrator role.",
            "is_system": True,
            "client_id": generate_client_id('base_role'),
        },
        {
            "id": 2,
            "role_name": "assistant",
            "description": "System assistant role.",
            "is_system": True,
            "client_id": generate_client_id('base_role'),
        },
        {
            "id": 3,
            "role_name": "driver",
            "description": "System driver role.",
            "is_system": True,
            "client_id": generate_client_id('base_role'),
        },
    ]

    user_roles = [
        {
            "id": 1,
            "role_name": "admin",
            "description": "Default admin user role.",
            "is_system": True,
            "client_id": generate_client_id('user_role'),
            "base_role_key": "admin",
        },
        {
            "id": 2,
            "role_name": "assistant",
            "description": "Default assistant user role.",
            "is_system": True,
            "client_id": generate_client_id('user_role'),
            "base_role_key": "assistant",
        },
        {
            "id": 3,
            "role_name": "driver",
            "description": "Default driver user role.",
            "is_system": True,
            "client_id": generate_client_id('user_role'),
            "base_role_key": "driver",
        },
    ]

    return base_roles, user_roles
