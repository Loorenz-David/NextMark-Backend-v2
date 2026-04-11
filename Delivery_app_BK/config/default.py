import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY","devkey")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    REDIS_URI = os.environ.get("REDIS_URI")
    REDIS_KEY_PREFIX = os.environ.get("REDIS_KEY_PREFIX", "nextmark")
    REDIS_DRIVER_LOCATION_TTL_SECONDS = int(os.environ.get("REDIS_DRIVER_LOCATION_TTL_SECONDS", "45"))
    REDIS_NOTIFICATION_TTL_SECONDS = int(os.environ.get("REDIS_NOTIFICATION_TTL_SECONDS", str(60 * 60 * 48)))
    REDIS_DISPATCHER_LEASE_SECONDS = int(os.environ.get("REDIS_DISPATCHER_LEASE_SECONDS", "120"))
    REDIS_DISPATCH_BATCH_SIZE = int(os.environ.get("REDIS_DISPATCH_BATCH_SIZE", "50"))
    REDIS_REPAIR_INTERVAL_SECONDS = int(os.environ.get("REDIS_REPAIR_INTERVAL_SECONDS", "60"))
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"options": "-c timezone=UTC"}
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ------------------------------------------------------------------
    # AI operator rollout flags (phased hardening)
    # ------------------------------------------------------------------
    AI_TOPIC_SESSIONS_ENABLED = os.environ.get("AI_TOPIC_SESSIONS_ENABLED", "true").lower() == "true"
    AI_TOPIC_AUTO_SWITCH_ENABLED = os.environ.get("AI_TOPIC_AUTO_SWITCH_ENABLED", "true").lower() == "true"
    AI_HISTORY_RESET_ON_TOPIC_SWITCH = os.environ.get("AI_HISTORY_RESET_ON_TOPIC_SWITCH", "true").lower() == "true"
    AI_CONTEXT_PACKING_ENABLED = os.environ.get("AI_CONTEXT_PACKING_ENABLED", "true").lower() == "true"
    AI_ROUTING_CONFIDENCE_ENABLED = os.environ.get("AI_ROUTING_CONFIDENCE_ENABLED", "true").lower() == "true"
    AI_ROUTING_DEFAULT_CAPABILITY = os.environ.get("AI_ROUTING_DEFAULT_CAPABILITY", "logistics")
    AI_CAPABILITY_MODE_ENABLED = os.environ.get("AI_CAPABILITY_MODE_ENABLED", "true").lower() == "true"
    AI_ROUTING_CONFIDENCE_FLOOR = float(os.environ.get("AI_ROUTING_CONFIDENCE_FLOOR", "0.50"))
    AI_ROUTING_ENABLE_STREAK_INFERENCE = os.environ.get("AI_ROUTING_ENABLE_STREAK_INFERENCE", "true").lower() == "true"
    AI_ROUTING_ENABLE_TOOL_INFERENCE = os.environ.get("AI_ROUTING_ENABLE_TOOL_INFERENCE", "true").lower() == "true"
    AI_CAPABILITY_POLICY_THREAD_LOCK_ENABLED = os.environ.get("AI_CAPABILITY_POLICY_THREAD_LOCK_ENABLED", "false").lower() == "true"
    AI_CAPABILITY_POLICY_INVALID_INPUT_BEHAVIOR = os.environ.get(
        "AI_CAPABILITY_POLICY_INVALID_INPUT_BEHAVIOR",
        "strict",
    ).strip().lower()
    AI_RESPONSE_CONTRACT_V2_ENABLED = os.environ.get("AI_RESPONSE_CONTRACT_V2_ENABLED", "false").lower() == "true"
    AI_EVAL_HARNESS_ENABLED = os.environ.get("AI_EVAL_HARNESS_ENABLED", "false").lower() == "true"

    AI_CAPABILITY_SHIFT_STREAK_THRESHOLD = int(os.environ.get("AI_CAPABILITY_SHIFT_STREAK_THRESHOLD", "2"))
    AI_PROPOSAL_TTL_SECONDS = int(
        os.environ.get("AI_PROPOSAL_TTL_SECONDS", str(60 * 60 * 24 * 30))
    )
    AI_PROPOSAL_APPLY_IDEMPOTENCY_TTL_SECONDS = int(
        os.environ.get("AI_PROPOSAL_APPLY_IDEMPOTENCY_TTL_SECONDS", str(60 * 60 * 24 * 30))
    )

    # ------------------------------------------------------------------
    # Web Push (VAPID)
    # ------------------------------------------------------------------
    WEB_PUSH_VAPID_PUBLIC_KEY = os.environ.get("WEB_PUSH_VAPID_PUBLIC_KEY")
    WEB_PUSH_VAPID_PRIVATE_KEY = os.environ.get("WEB_PUSH_VAPID_PRIVATE_KEY")
    WEB_PUSH_VAPID_SUBJECT = os.environ.get("WEB_PUSH_VAPID_SUBJECT", "mailto:admin@nextmark.app")



def resolve_env_path(config_name: str) -> str | None:
    if config_name == "production":
        env_path = "/home/ubuntu/config/nextmark/.env"
    else:
        env_path = ".env"

    if os.path.exists(env_path):
        return env_path

    if config_name == "production":
        raise RuntimeError(f"Missing required env file at {env_path}")

    return None