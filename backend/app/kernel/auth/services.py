from app.kernel.models import User


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "grade": user.grade,
        "school": user.school,
        "main_subject": user.main_subject,
    }
