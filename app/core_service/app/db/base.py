# Import all the models, so that Base has them before being
# imported by Alembic
from app.db.base_class import Base  # noqa
from app.models.training import Training  # noqa
from app.models.module import Module  # noqa
from app.models.chapter import Chapter  # noqa
from app.models.progress import UserProgress  # noqa
from app.models.enrollment import Enrollment  # noqa
from app.models.training_history import TrainingHistory  # noqa
from app.models.assignment import TrainingAssignment  # noqa
from app.models.quiz_attempt import QuizAttempt  # noqa
from app.models.audit_log import AuditLog  # noqa
from app.models.collaborator import TrainingCollaborator  # noqa
from app.models.certificate import Certificate  # noqa
from app.models.certificate_template import CertificateTemplate  # noqa
from app.models.category import TrainingCategory  # noqa
