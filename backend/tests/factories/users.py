import factory

from app.domains.auth.models import Role, User
from app.domains.auth.security import hash_password


class RoleFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Role
        sqlalchemy_session = None  # To be overridden dynamically or passed in
        sqlalchemy_session_persistence = "commit"

    name = "TEST_ROLE"


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    full_name = factory.Faker("name")
    password_hash = factory.LazyFunction(lambda: hash_password("Password@123"))
    role = factory.SubFactory(RoleFactory)
    is_active = True
