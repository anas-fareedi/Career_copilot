# Models package — import all models here so SQLAlchemy metadata is fully populated
# when Base.metadata.create_all() is called in main.py lifespan.
from APP.models.base import Base  # noqa: F401
from APP.models.user import User, UserPreferences  # noqa: F401
from APP.models.jobs import DiscoveredJob, Application, ApplicationStatus  # noqa: F401
from APP.models.resume import ResumeVersion  # noqa: F401
