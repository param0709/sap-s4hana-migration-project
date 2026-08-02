"""ORM models. Importing this package registers every table on Base.metadata."""
from app.models.migration_project import MigrationProject
from app.models.migration_issue import MigrationIssue
from app.models.migration_record import MigrationRecord
from app.models.uploaded_file import UploadedFile

__all__ = ["MigrationIssue", "MigrationProject", "MigrationRecord", "UploadedFile"]
