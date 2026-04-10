from Delivery_app_BK.models import db, OAuthState

def save_oauth_state(state, user_id, team_id, expires_at):
    db.session.add(
        OAuthState(
            state=state,
            user_id=user_id, 
            team_id = team_id,
            expires_at=expires_at
        )
    )
    db.session.commit()


def get_oauth_state(state):
    return OAuthState.query.filter_by(state=state).first()

def delete_oauth_state(state):
    OAuthState.query.filter_by(state=state).delete()
    db.session.commit()