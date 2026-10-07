from .validation import ValidationFailed


class TeamMembershipConflict(ValidationFailed):
    code = "team_membership_conflict"
