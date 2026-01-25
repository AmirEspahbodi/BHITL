import logging

from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.models import User, UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db(session: Session) -> None:
    for data in [
        (settings.USER_1_EMAIL, settings.USER_1_PASSWORD, settings.USER_1_FULL_NAME),
        (settings.USER_2_EMAIL, settings.USER_2_PASSWORD, settings.USER_2_FULL_NAME),
        (settings.USER_3_EMAIL, settings.USER_3_PASSWORD, settings.USER_3_FULL_NAME),
    ]:
        email, password, full_name = data
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user_in = UserCreate(
                email=email,
                password=password,
                full_name=full_name,
                is_superuser=False,
            )
            user = crud.create_user(session=session, user_create=user_in)


def init() -> None:
    with Session(engine) as session:
        init_db(session)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
