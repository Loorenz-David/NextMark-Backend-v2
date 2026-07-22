
class ServiceContext():

    def __init__( 
            self,
            incoming_data=None,
            incoming_file=None,
            query_params=None,
            identity=None,
            check_team_id = True,
            inject_team_id = True,
            skip_id_instance_injection = True,
            relationship_map = None,
            on_create_return = "map_ids_object",
            on_query_return = "client_ids_map",
            allow_is_system_modification = False,
            extract_fields_key = True,
            prevent_event_bus = False,
            request_ip = None,
            user_agent = None,
            trusted_device_client_id = None,
            trusted_device_secret = None
    ):
        self.incoming_data = incoming_data or {}
        self.incoming_file = incoming_file or None
        self.query_params = query_params or {}
        self.identity = identity or {}
        self.warnings = []
        # Request metadata for security auditing (never logged by run_service).
        self.request_ip = request_ip
        self.user_agent = user_agent
        # Trusted-device credentials, resolved from headers by the router.
        # Kept off incoming_data/identity so the secret is never serialized
        # into error logs.
        self.trusted_device_client_id = trusted_device_client_id
        self.trusted_device_secret = trusted_device_secret
        self.check_team_id = check_team_id
        self.inject_team_id = inject_team_id
        self.skip_id_instance_injection = skip_id_instance_injection 
        self.relationship_map = relationship_map or {}
        self.on_create_return = on_create_return
        self.on_query_return = on_query_return
        self.allow_is_system_modification = allow_is_system_modification 
        self.extract_fields_key = extract_fields_key
        self.prevent_event_bus = prevent_event_bus
        # Set by the AI orchestrator to scope tool-access enforcement per operation
        self.ai_operation: str | None = None
    
    def set_warning( self, message ):
        return self.warnings.append( message )

    def set_relationship_map( self, map ):
        self.relationship_map = map
        return self
    
    def upsert_relationship_map( self, map):
        self.relationsip_map = {
            ** self.relationship_map,
            **map
        }
        return self

    @property
    def team_id( self ):
        return self.identity.get("active_team_id", self.identity.get("team_id"))
    
    @property
    def user_id ( self ):
        return self.identity.get( "user_id" )
    
    @property
    def role_id ( self ):
        return self.identity.get("role_id", self.identity.get("user_role_id"))
    
    @property
    def base_role_id ( self ):
        return self.identity.get( "base_role_id" )

    @property
    def app_scope(self):
        return self.identity.get("app_scope")

    @property
    def session_scope_id(self):
        return self.identity.get("session_scope_id")

    @property
    def current_workspace(self):
        return self.identity.get("current_workspace")

    @property
    def active_team_id(self):
        return self.identity.get("active_team_id", self.identity.get("team_id"))

    @property
    def time_zone(self):
        return self.identity.get("time_zone")

    @property
    def default_country_code(self):
        return self.identity.get("default_country_code")

    @property
    def default_city_key(self):
        return self.identity.get("default_city_key")
