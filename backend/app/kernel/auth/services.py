from app.kernel.models import User


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "grade": user.grade,
        "school": user.school,
        "main_subject": user.main_subject,
        "role": user.role,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }
