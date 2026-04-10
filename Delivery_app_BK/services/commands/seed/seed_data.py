from ..utils.client_id_generator import generate_client_id


def build_seed_payloads():
    base_roles = [
        {
            "id": 1,
            "role_name": "ADMIN",
            "description": "System administrator role.",
            "is_system": True,
            "client_id": generate_client_id('base_role'),
        },
        {
            "id": 2,
            "role_name": "ASSISTANT",
            "description": "System assistant role.",
            "is_system": True,
            "client_id": generate_client_id('base_role'),
        },
        {
            "id": 3,
            "role_name": "DRIVER",
            "description": "System driver role.",
            "is_system": True,
            "client_id": generate_client_id('base_role'),
        },
    ]

    user_roles = [
        {
            "id": 1,
            "role_name": "Admin",
            "description": "Default admin user role.",
            "is_system": True,
            "client_id": generate_client_id('user_role'),
            "base_role_key": "ADMIN",
        },
        {
            "id": 2,
            "role_name": "Assistant",
            "description": "Default assistant user role.",
            "is_system": True,
            "client_id": generate_client_id('user_role'),
            "base_role_key": "ASSISTANT",
        },
        {
            "id": 3,
            "role_name": "Driver",
            "description": "Default driver user role.",
            "is_system": True,
            "client_id": generate_client_id('user_role'),
            "base_role_key": "DRIVER",
        },
    ]

    return base_roles, user_roles
