from datetime import date

from sqlmodel import Session, func, select

from app.core.errors import field_error, validation_error
from app.core.security import hash_password, is_strong_password, verify_password
from app.models import Avatar, EmailTokenPurpose, Survey, User
from app.models.base import utcnow
from app.schemas import generated as api
from app.services.email import EmailSender, link
from app.services.tokens import issue_email_token

MIN_AGE = 18


def age_on(birthday: date, today: date) -> int:
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def to_user_schema(session: Session, user: User) -> api.User:
    survey = session.get(Survey, user.id)
    return api.User(
        id=user.id,
        email=user.email,
        pending_email=user.pending_email,
        email_verified=user.email_verified,
        first_name=user.first_name,
        last_name=user.last_name,
        birthday=user.birthday,
        age=age_on(user.birthday, date.today()),
        address=api.Address.model_validate(user.address) if user.address else None,
        avatar_id=user.avatar_id,
        onboarding_completed=user.onboarding_completed,
        diet=api.Diet(survey.diet) if survey and survey.diet else None,
        created_at=user.created_at,
    )


def find_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(func.lower(User.email) == email.lower())).first()


def password_errors(password: str, confirm: str, field: str, confirm_field: str):
    errors = []
    if not is_strong_password(password):
        errors.append(
            field_error(
                field,
                api.Code.WEAK_PASSWORD,
                "Use at least 12 characters with upper and lower case letters, a number and a symbol.",
            )
        )
    if password != confirm:
        errors.append(
            field_error(confirm_field, api.Code.PASSWORD_MISMATCH, "Passwords do not match.")
        )
    return errors


def birthday_errors(birthday: date) -> list[api.FieldError]:
    if age_on(birthday, date.today()) < MIN_AGE:
        return [field_error("birthday", api.Code.UNDERAGE, "You must be at least 18 years old.")]
    return []


def update_user(
    session: Session, user: User, body: api.UserUpdate, email_sender: EmailSender
) -> User:
    fields = body.model_fields_set
    if not fields:
        raise validation_error(
            [field_error("body", api.Code.REQUIRED, "Provide at least one field.")]
        )

    errors: list[api.FieldError] = []
    for name in ("first_name", "last_name", "email", "birthday"):
        if name in fields and getattr(body, name) is None:
            errors.append(field_error(name, api.Code.REQUIRED, "This field cannot be empty."))
    if body.birthday is not None:
        errors += birthday_errors(body.birthday)
    new_email = None
    if body.email is not None and body.email.lower() != user.email.lower():
        if find_by_email(session, body.email):
            errors.append(
                field_error("email", api.Code.EMAIL_IN_USE, "This email is already in use.")
            )
        else:
            new_email = body.email
    if (
        "avatar_id" in fields
        and body.avatar_id is not None
        and not session.get(Avatar, body.avatar_id)
    ):
        errors.append(field_error("avatar_id", api.Code.INVALID_VALUE, "Unknown avatar."))
    if errors:
        raise validation_error(errors)

    for name in ("first_name", "last_name", "birthday"):
        if getattr(body, name) is not None:
            setattr(user, name, getattr(body, name))
    if "address" in fields:
        user.address = body.address.model_dump(mode="json") if body.address else None
    if "avatar_id" in fields:
        user.avatar_id = body.avatar_id
    if new_email:
        user.pending_email = new_email
        token = issue_email_token(
            session, user, EmailTokenPurpose.CHANGE_EMAIL, new_email=new_email
        )
        email_sender.send(
            new_email,
            "Confirm your new email address",
            f"Confirm your new Rooted email address: {link('verify-email', token)}",
        )
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def change_password(session: Session, user: User, body: api.ChangePasswordRequest) -> None:
    new_password = body.new_password.root.get_secret_value()
    errors = []
    if not verify_password(body.current_password.get_secret_value(), user.password_hash):
        errors.append(
            field_error(
                "current_password", api.Code.INCORRECT_PASSWORD, "Current password is incorrect."
            )
        )
    errors += password_errors(
        new_password,
        body.new_password_confirm.get_secret_value(),
        "new_password",
        "new_password_confirm",
    )
    if errors:
        raise validation_error(errors)
    user.password_hash = hash_password(new_password)
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
